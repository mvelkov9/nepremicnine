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
from app.services.data_processing_service import prepare_training_csv_from_etn_kpp_bulk
from app.services.model_service import invalidate_model_cache, train_from_csv
from app.utils.cache import invalidate_cache_prefixes

logger = logging.getLogger(__name__)

JOB_PREFIX = "training_job:"
PREPARE_JOB_PREFIX = "prepare_job:"
PREPARE_ACTIVE_KEY = "prepare_job:active"
INTERRUPTED_TRAINING_ERROR = "Training interrupted because the worker restarted. Requeue the job."
INTERRUPTED_PREPARE_ERROR = "Preparation interrupted because the worker restarted. Requeue the job."


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


async def _fail_interrupted_training_jobs(redis) -> None:
    async with async_session() as session:
        result = await session.execute(select(TrainingJob).where(TrainingJob.status == JobStatus.running))
        jobs = result.scalars().all()
        if not jobs:
            return

        now = time.time()
        for job in jobs:
            job.status = JobStatus.failed
            job.stage = "error"
            job.error = INTERRUPTED_TRAINING_ERROR
            await redis.set(
                f"{JOB_PREFIX}{job.job_id}",
                json.dumps(
                    {
                        "status": "failed",
                        "stage": "error",
                        "progress": job.progress,
                        "rows": job.rows,
                        "current_model": job.current_model,
                        "current_model_index": job.current_model_index,
                        "total_models": job.total_models,
                        "current_model_progress": job.current_model_progress,
                        "fitted_trees": job.fitted_trees,
                        "total_trees": job.total_trees,
                        "elapsed_sec": job.elapsed_sec,
                        "eta_sec": job.eta_sec,
                        "error": INTERRUPTED_TRAINING_ERROR,
                        "updated_at": now,
                    }
                ),
                ex=86400,
            )

        await session.commit()
        logger.warning("Marked %s interrupted training job(s) as failed after worker startup", len(jobs))


async def _fail_interrupted_prepare_job(redis) -> None:
    active_job_id = await redis.get(PREPARE_ACTIVE_KEY)
    if active_job_id is None:
        return

    if isinstance(active_job_id, bytes):
        active_job_id = active_job_id.decode("utf-8", errors="ignore")

    await redis.set(
        f"{PREPARE_JOB_PREFIX}{active_job_id}",
        json.dumps(
            {
                "status": "failed",
                "stage": "error",
                "error": INTERRUPTED_PREPARE_ERROR,
                "updated_at": time.time(),
            }
        ),
        ex=86400,
    )
    await redis.delete(PREPARE_ACTIVE_KEY)
    logger.warning("Marked interrupted prepare job %s as failed after worker startup", active_job_id)


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
        result = await asyncio.to_thread(
            train_from_csv,
            csv_path,
            None,
            status_callback,
            benchmark_per_type_variants=True,
        )
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


async def run_prepare_etn_bulk(
    ctx: dict,
    job_id: str,
    pairs: list[dict],
    output_csv_path: str,
    enrichment_options: dict | None = None,
) -> dict:
    """ARQ task: prepare ETN bulk dataset with progress updates stored in Redis."""
    redis = ctx["redis"]
    key = f"{PREPARE_JOB_PREFIX}{job_id}"
    loop = asyncio.get_running_loop()
    pending_updates: set[asyncio.Task] = set()

    async def _set_state(payload: dict) -> None:
        await redis.set(key, json.dumps(payload), ex=86400)

    async def _set_active() -> None:
        await redis.set(PREPARE_ACTIVE_KEY, job_id, ex=86400)

    async def _publish(payload: dict) -> None:
        cleaned = {field: value for field, value in payload.items() if value is not None}
        await _set_active()
        await _set_state(cleaned)

    def _schedule(payload: dict) -> None:
        def _create_task() -> None:
            task = loop.create_task(_publish(payload))
            pending_updates.add(task)
            task.add_done_callback(lambda finished: pending_updates.discard(finished))

        loop.call_soon_threadsafe(_create_task)

    await _set_active()
    await _set_state(
        {
            "status": "running",
            "stage": "initializing",
            "progress": 0,
            "total_pairs": len(pairs),
            "pairs_completed": 0,
        }
    )

    def status_callback(stage: str, **state) -> None:
        _schedule({"status": "running", "stage": stage, **state})

    try:
        result = await asyncio.to_thread(
            prepare_training_csv_from_etn_kpp_bulk,
            pairs,
            output_csv_path,
            status_callback,
            enrichment_options,
        )
        if pending_updates:
            await asyncio.gather(*pending_updates, return_exceptions=True)
        await _set_state(
            {
                "status": "completed",
                "stage": "completed",
                "progress": 100,
                "total_pairs": len(pairs),
                "pairs_completed": result.get("pairs_used", len(pairs)),
                "rows": result.get("rows"),
                "result": result,
            }
        )
        await redis.delete(PREPARE_ACTIVE_KEY)
        await invalidate_cache_prefixes(redis)
        return result
    except Exception as exc:
        logger.exception("ETN bulk preparation failed for job %s", job_id)
        if pending_updates:
            await asyncio.gather(*pending_updates, return_exceptions=True)
        await _set_state(
            {
                "status": "failed",
                "stage": "error",
                "error": str(exc),
                "total_pairs": len(pairs),
            }
        )
        await redis.delete(PREPARE_ACTIVE_KEY)
        raise


async def startup(ctx: dict):
    """ARQ worker startup — store redis connection in context and reconcile interrupted jobs."""
    settings = get_settings()
    ctx["redis"] = await create_pool(_parse_redis_url(settings.redis_url))
    await _fail_interrupted_training_jobs(ctx["redis"])
    await _fail_interrupted_prepare_job(ctx["redis"])


async def shutdown(ctx: dict):
    """ARQ worker shutdown."""
    redis = ctx.get("redis")
    if redis:
        await redis.close()


class WorkerSettings:
    """ARQ worker configuration."""

    functions = [run_training, run_prepare_etn_bulk]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = _parse_redis_url(get_settings().redis_url)
    max_jobs = 1  # Only one training at a time
    job_timeout = max(3600, int(get_settings().training_job_timeout_sec))  # Effectively unbounded for training
