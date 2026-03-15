"""Auth service: password hashing, JWT creation."""

from datetime import UTC, datetime, timedelta

import bcrypt
from jose import jwt

from app.config import get_settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user_id), "type": "access", "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: int) -> str:
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    payload = {"sub": str(user_id), "type": "refresh", "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


async def blacklist_token(redis, token: str, ttl_seconds: int) -> None:
    """Add a token to the blacklist in Redis with TTL matching token expiry."""
    await redis.set(f"token_blacklist:{token}", "1", ex=ttl_seconds)


async def is_token_blacklisted(redis, token: str) -> bool:
    """Check if a token has been blacklisted."""
    result = await redis.get(f"token_blacklist:{token}")
    return result is not None
