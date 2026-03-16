"""Auth routes: register, login, refresh, me, logout."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.dependencies.auth import get_current_user, security
from app.models.user import User, UserRole
from app.rate_limit import limiter
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import (
    blacklist_token,
    create_access_token,
    create_refresh_token,
    hash_password,
    is_token_blacklisted,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(request: Request, body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # Check duplicate email
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    # First user → admin, rest → viewer (serialised to avoid TOCTOU race)
    async with db.begin_nested():
        await db.execute(text("SELECT pg_advisory_xact_lock(12345678)"))
        count = await db.execute(select(func.count(User.id)))
        is_first = count.scalar() == 0

        user = User(
            email=body.email,
            hashed_password=hash_password(body.password),
            full_name=body.full_name,
            role=UserRole.admin if is_first else UserRole.viewer,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("10/minute")
async def refresh(request: Request, body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    settings = get_settings()
    try:
        payload = jwt.decode(
            body.refresh_token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id = payload.get("sub")
        token_type = payload.get("type")
        if not user_id or token_type != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from None

    # Reject blacklisted refresh tokens
    if await is_token_blacklisted(request.app.state.redis, body.refresh_token):
        raise HTTPException(status_code=401, detail="Refresh token has been revoked")

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return user


@router.post("/logout")
async def logout(
    request: Request,
    body: LogoutRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    _user: User = Depends(get_current_user),
):
    """Blacklist the access token (and optionally the refresh token)."""
    settings = get_settings()

    # Blacklist access token using its own exp claim for accurate TTL
    try:
        access_payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        access_ttl = max(0, int(access_payload["exp"] - datetime.now(UTC).timestamp()))
    except JWTError:
        access_ttl = settings.access_token_expire_minutes * 60
    await blacklist_token(request.app.state.redis, credentials.credentials, access_ttl)

    # Blacklist refresh token if provided
    if body.refresh_token:
        try:
            ref_payload = jwt.decode(
                body.refresh_token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )
            if ref_payload.get("type") == "refresh":
                ref_ttl = max(0, int(ref_payload["exp"] - datetime.now(UTC).timestamp()))
                await blacklist_token(request.app.state.redis, body.refresh_token, ref_ttl)
        except JWTError:
            pass  # invalid refresh token — nothing to revoke

    return {"detail": "Logged out"}
