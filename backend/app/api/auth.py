"""Auth routes: register, login, refresh, me, logout."""

from datetime import UTC, datetime

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.dependencies.auth import ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME, get_current_user, security
from app.models.user import User, UserRole
from app.rate_limit import limiter
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
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


def _set_auth_cookie(response: Response, name: str, value: str, max_age: int, settings) -> None:
    response.set_cookie(
        key=name,
        value=value,
        max_age=max_age,
        expires=max_age,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/",
    )


def _clear_auth_cookie(response: Response, name: str, settings) -> None:
    response.delete_cookie(
        key=name,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/",
    )


def _read_refresh_token(body_token: str | None, cookie_token: str | None) -> str | None:
    return body_token or cookie_token


def _normalize_avatar_url(raw_value: str | None) -> str | None:
    if raw_value is None:
        return None
    value = raw_value.strip()
    if not value:
        return None
    if not (value.startswith("https://") or value.startswith("data:image/") or value.startswith("/")):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid avatar URL")
    return value


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(request: Request, body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # Check duplicate email
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Registration failed")

    # First user → admin, rest → viewer (serialised to avoid TOCTOU race)
    async with db.begin_nested():
        # pg_advisory_xact_lock is PostgreSQL-only; skip on other DBs (e.g. SQLite in tests)
        settings_inner = get_settings()
        if "postgresql" in settings_inner.database_url:
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
async def login(request: Request, response: Response, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    settings = get_settings()
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    _set_auth_cookie(response, ACCESS_COOKIE_NAME, access_token, settings.access_token_expire_minutes * 60, settings)
    _set_auth_cookie(response, REFRESH_COOKIE_NAME, refresh_token, settings.refresh_token_expire_days * 24 * 60 * 60, settings)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("10/minute")
async def refresh(
    request: Request,
    response: Response,
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    refresh_token_cookie: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
):
    settings = get_settings()
    refresh_token = _read_refresh_token(body.refresh_token, refresh_token_cookie)
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    try:
        payload = jwt.decode(
            refresh_token,
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
    if await is_token_blacklisted(request.app.state.redis, refresh_token):
        raise HTTPException(status_code=401, detail="Refresh token has been revoked")

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    # Invalidate the consumed refresh token (token rotation)
    old_ttl = max(0, int(payload["exp"] - datetime.now(UTC).timestamp()))
    await blacklist_token(request.app.state.redis, refresh_token, old_ttl)

    access_token = create_access_token(user.id)
    next_refresh_token = create_refresh_token(user.id)
    _set_auth_cookie(response, ACCESS_COOKIE_NAME, access_token, settings.access_token_expire_minutes * 60, settings)
    _set_auth_cookie(
        response,
        REFRESH_COOKIE_NAME,
        next_refresh_token,
        settings.refresh_token_expire_days * 24 * 60 * 60,
        settings,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=next_refresh_token,
    )


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserResponse)
async def update_profile(
    body: UpdateProfileRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if body.full_name is None and body.avatar_url is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No profile changes submitted")

    if body.full_name is not None:
        full_name = body.full_name.strip()
        if not full_name:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Full name is required")
        user.full_name = full_name

    if body.avatar_url is not None:
        user.avatar_url = _normalize_avatar_url(body.avatar_url)

    await db.commit()
    await db.refresh(user)
    return user


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    body: LogoutRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    access_token_cookie: str | None = Cookie(default=None, alias=ACCESS_COOKIE_NAME),
    refresh_token_cookie: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
    _user: User = Depends(get_current_user),
):
    """Blacklist the access token (and optionally the refresh token)."""
    settings = get_settings()
    access_token = credentials.credentials if credentials and credentials.credentials else access_token_cookie
    refresh_token = _read_refresh_token(body.refresh_token, refresh_token_cookie)

    # Blacklist access token using its own exp claim for accurate TTL
    if access_token:
        try:
            access_payload = jwt.decode(
                access_token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )
            access_ttl = max(0, int(access_payload["exp"] - datetime.now(UTC).timestamp()))
        except JWTError:
            access_ttl = settings.access_token_expire_minutes * 60
        await blacklist_token(request.app.state.redis, access_token, access_ttl)

    # Blacklist refresh token if provided
    if refresh_token:
        try:
            ref_payload = jwt.decode(
                refresh_token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )
            if ref_payload.get("type") == "refresh":
                ref_ttl = max(0, int(ref_payload["exp"] - datetime.now(UTC).timestamp()))
                await blacklist_token(request.app.state.redis, refresh_token, ref_ttl)
        except JWTError:
            pass  # invalid refresh token — nothing to revoke

    _clear_auth_cookie(response, ACCESS_COOKIE_NAME, settings)
    _clear_auth_cookie(response, REFRESH_COOKIE_NAME, settings)

    return {"detail": "Logged out"}
