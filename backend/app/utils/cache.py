"""Shared Redis cache helpers."""

import json
import logging
from collections.abc import Sequence

from fastapi import Request

logger = logging.getLogger(__name__)

CACHE_TTL = 300  # 5 minutes
DEFAULT_CACHE_PREFIXES = (
    "cache:stats:",
    "cache:model:",
    "cache:regions:",
    "cache:data:",
    "cache:workbench:",
    "cache:activity:",
    "cache:admin:",
)
_ZERO_CURSORS = {0, "0", b"0"}


async def cache_get(request: Request, key: str) -> dict | list | None:
    """Try to get cached value from Redis. Returns None on miss or error."""
    try:
        redis = getattr(request.app.state, "redis", None)
        if redis is None:
            return None
        raw = await redis.get(key)
        if raw is not None:
            return json.loads(raw)
    except Exception:
        logger.debug("Redis cache miss/error for key=%s", key)
    return None


async def cache_set(request: Request, key: str, value, ttl: int = CACHE_TTL) -> None:
    """Store value in Redis cache with TTL. Silently ignores errors."""
    try:
        redis = getattr(request.app.state, "redis", None)
        if redis is None:
            return
        await redis.set(key, json.dumps(value, default=str), ex=ttl)
    except Exception:
        logger.debug("Redis cache set error for key=%s", key)


async def invalidate_cache_prefixes(
    redis,
    prefixes: Sequence[str] = DEFAULT_CACHE_PREFIXES,
) -> int:
    """Delete all cached keys matching the given prefixes."""
    if redis is None:
        return 0

    deleted = 0
    try:
        for prefix in prefixes:
            cursor: int | str | bytes = 0
            while True:
                cursor, keys = await redis.scan(cursor=cursor, match=f"{prefix}*", count=100)
                if keys:
                    await redis.delete(*keys)
                    deleted += len(keys)
                if cursor in _ZERO_CURSORS:
                    break
    except Exception:
        logger.debug("Redis cache invalidation error for prefixes=%s", prefixes)
        return 0

    return deleted


async def invalidate_request_caches(
    request: Request,
    prefixes: Sequence[str] = DEFAULT_CACHE_PREFIXES,
) -> int:
    """Invalidate cached HTTP responses for the current FastAPI app."""
    redis = getattr(request.app.state, "redis", None)
    return await invalidate_cache_prefixes(redis, prefixes=prefixes)
