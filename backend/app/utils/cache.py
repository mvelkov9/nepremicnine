"""Shared Redis cache helpers."""

import json
import logging

from fastapi import Request

logger = logging.getLogger(__name__)

CACHE_TTL = 300  # 5 minutes


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
