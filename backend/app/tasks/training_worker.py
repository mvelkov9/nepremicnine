"""ARQ worker — async training task with progress reporting via Redis."""

from __future__ import annotations

import asyncio
import json
import logging
import time

from arq import create_pool
from arq.connections import RedisSettings
from sqlalchemy import select

from app.config import get_settings
from app.database import async_session
from app.models.model_run import ModelRun
from app.models.training_job import JobStatus, TrainingJob
from app.services.model_service import invalidate_model_cache, train_from_csv
from app.utils.cache import invalidate_cache_prefixes

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


async def _update_job_record(job_id: str, **fields) -> None:
    async with async_session() as session:
        result = await session.execute(select(TrainingJob).where(TrainingJob.job_id == job_id))
        job = result.scalar_one_or_none()
        if job is None:
            return
        for key, value in fields.items():
            setattr(job, key, value)
        await session.commit()


async def _record_model_run(csv_path: str, result: dict) -> None:
    metrics = result.get("global_metrics") or {}
    async with async_session() as session:
        session.add(
            ModelRun(
                source_csv_path=csv_path,
                rows=result.get("rows"),
                mae=metrics.get("mae"),
                rmse=metrics.get("rmse"),
                r2=metrics.get("r2"),
                mape=metrics.get("mape"),
                median_ae=metrics.get("median_ae"),
                duration_sec=result.get("duration_sec"),
                per_type_count=result.get("per_type_count"),
                model_type=result.get("model_type"),
                features_json=json.dumps(result.get("used_features") or []),
                importance_json=json.dumps(result.get("global_importance") or {}),
                combined_metrics_json=json.dumps(result.get("combined_metrics") or {}),
            )
        )
        await session.commit()


async def run_training(ctx: dict, job_id: str, csv_path: str) -> dict:
    """ARQ task: train model from CSV with progress updates stored in Redis."""
    redis = ctx["redis"]
    key = f"{JOB_PREFIX}{job_id}"
    loop = asyncio.get_running_loop()
    pending_updates: set[asyncio.Task] = set()

    async def _update(status: str, **extra):
        data = {"status": status, "updated_at": time.time(), **extra}
        await redis.set(key, json.dumps(data), ex=86400)

    async def _publish_progress(payload: dict) -> None:
        cleaned = {key: value for key, value in payload.items() if value is not None}
        await _update("running", **cleaned)
        await _update_job_record(job_id, status=JobStatus.running, error=None, **cleaned)

    def _schedule_progress(payload: dict) -> None:
        def _create_task():
            task = loop.create_task(_publish_progress(payload))
            pending_updates.add(task)
            task.add_done_callback(lambda finished: pending_updates.discard(finished))

        loop.call_soon_threadsafe(_create_task)

    await _update("running", stage="initializing", progress=0, current_model_progress=0)
    await _update_job_record(
        job_id,
        status=JobStatus.running,
        stage="initializing",
        progress=0,
        current_model_progress=0,
        error=None,
    )

    def status_callback(stage: str, **state):
        payload = {"stage": stage, **state}
        _schedule_progress(payload)

    try:
        result = await asyncio.to_thread(train_from_csv, csv_path, None, status_callback)
        if pending_updates:
            await asyncio.gather(*pending_updates, return_exceptions=True)
        invalidate_model_cache()
        await _record_model_run(csv_path, result)
        await _update_job_record(
            job_id,
            status=JobStatus.completed,
            stage="done",
            progress=100,
            rows=result.get("rows"),
            duration_sec=result.get("duration_sec"),
            current_model="done",
            current_model_progress=100,
            current_model_index=result.get("per_type_count", 0) + 1,
            total_models=result.get("per_type_count", 0) + 1,
            elapsed_sec=result.get("duration_sec"),
            error=None,
        )
        await _update(
            "completed",
            stage="done",
            progress=100,
            rows=result.get("rows"),
            current_model="done",
            current_model_progress=100,
            current_model_index=result.get("per_type_count", 0) + 1,
            total_models=result.get("per_type_count", 0) + 1,
            elapsed_sec=result.get("duration_sec"),
            result=result,
        )
        await invalidate_cache_prefixes(redis)
        return result
    except Exception as exc:
        logger.exception("Training failed for job %s", job_id)
        if pending_updates:
            await asyncio.gather(*pending_updates, return_exceptions=True)
        await _update_job_record(job_id, status=JobStatus.failed, stage="error", error=str(exc))
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
