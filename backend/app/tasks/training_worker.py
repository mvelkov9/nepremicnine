"""ARQ worker — async training task with progress reporting via Redis."""

from __future__ import annotations

import json
import logging
import time

from arq import create_pool
from arq.connections import RedisSettings

from app.config import get_settings
from app.services.model_service import train_from_csv

logger = logging.getLogger(__name__)

JOB_PREFIX = "training_job:"


def _parse_redis_url(url: str) -> RedisSettings:
    """Convert redis://host:port/db to RedisSettings."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return RedisSettings(
        host=parsed.hostname or "redis",
        port=parsed.port or 6379,
        database=int(parsed.path.lstrip("/") or 0),
    )


async def run_training(ctx: dict, job_id: str, csv_path: str) -> dict:
    """ARQ task: train model from CSV with progress updates stored in Redis."""
    redis = ctx["redis"]
    key = f"{JOB_PREFIX}{job_id}"

    async def _update(status: str, **extra):
        data = {"status": status, "updated_at": time.time(), **extra}
        await redis.set(key, json.dumps(data), ex=86400)

    await _update("running", stage="initializing", progress=0)

    def progress_callback(label: str, fitted: int, total: int):
        pct = round(fitted / total * 100, 1) if total > 0 else 0
        # Store progress in a simple way; the async update happens periodically
        ctx["_progress"] = {
            "label": label,
            "fitted": fitted,
            "total": total,
            "pct": pct,
        }

    try:
        result = train_from_csv(csv_path, progress_callback=progress_callback)
        await _update(
            "completed",
            stage="done",
            progress=100,
            result=result,
        )
        return result
    except Exception as exc:
        logger.exception("Training failed for job %s", job_id)
        await _update("failed", stage="error", error=str(exc))
        raise


async def startup(ctx: dict):
    """ARQ worker startup — store redis connection in context."""
    settings = get_settings()
    ctx["redis"] = await create_pool(_parse_redis_url(settings.redis_url))


async def shutdown(ctx: dict):
    """ARQ worker shutdown."""
    redis = ctx.get("redis")
    if redis:
        await redis.close()


class WorkerSettings:
    """ARQ worker configuration."""

    functions = [run_training]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = _parse_redis_url(get_settings().redis_url)
    max_jobs = 1  # Only one training at a time
    job_timeout = 3600  # 1 hour max
