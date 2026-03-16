"""Training routes — start training, check status, list jobs."""

from __future__ import annotations

import json
import logging
import math
import os
import uuid
from datetime import UTC, datetime, timedelta

from arq import create_pool
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.dependencies.auth import get_current_user, require_admin
from app.models.training_job import JobStatus, TrainingJob
from app.models.user import User
from app.schemas.model import TrainJobResponse, TrainRequest, TrainStatusResponse
from app.tasks.training_worker import JOB_PREFIX, _parse_redis_url
from app.utils.cache import invalidate_request_caches

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/train", tags=["training"])

DATA_DIR = os.path.realpath(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"))

ACTIVE_JOB_STATUSES = (JobStatus.queued, JobStatus.running)
QUEUED_JOB_STALE_AFTER = timedelta(minutes=15)
RUNNING_JOB_STALE_AFTER = timedelta(hours=2)


def _to_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _coerce_progress(value: object, fallback: int = 0) -> int:
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return fallback


async def _read_redis_job_state(redis, job_id: str) -> dict | None:
    raw = await redis.get(f"{JOB_PREFIX}{job_id}")
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="ignore")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Ignoring invalid Redis training payload for job %s", job_id)
        return None


def _serialize_job(job: TrainingJob, state: dict | None = None) -> TrainStatusResponse:
    payload = state or {}
    status_value = payload.get("status")
    progress_value = payload.get("progress")
    return TrainStatusResponse(
        job_id=job.job_id,
        status=status_value or (job.status.value if isinstance(job.status, JobStatus) else str(job.status)),
        stage=payload.get("stage") or job.stage,
        progress=_coerce_progress(progress_value, fallback=job.progress or 0),
        rows=payload.get("rows") or job.rows,
        current_model=payload.get("current_model") or job.current_model,
        current_model_index=payload.get("current_model_index") or job.current_model_index,
        total_models=payload.get("total_models") or job.total_models,
        current_model_progress=_coerce_progress(
            payload.get("current_model_progress"),
            fallback=job.current_model_progress or 0,
        )
        if payload.get("current_model_progress") is not None or job.current_model_progress is not None
        else None,
        fitted_trees=payload.get("fitted_trees") or job.fitted_trees,
        total_trees=payload.get("total_trees") or job.total_trees,
        elapsed_sec=payload.get("elapsed_sec") or job.elapsed_sec,
        eta_sec=payload.get("eta_sec") or job.eta_sec,
        result=payload.get("result"),
        error=payload.get("error") or job.error,
    )


def _job_is_stale(job: TrainingJob, now: datetime) -> bool:
    threshold = RUNNING_JOB_STALE_AFTER if job.status == JobStatus.running else QUEUED_JOB_STALE_AFTER
    reference_time = _to_utc(job.updated_at or job.created_at)
    return now - reference_time > threshold


async def _reconcile_active_job(db: AsyncSession, redis) -> tuple[TrainingJob | None, dict | None]:
    """Return the most recent live training job and mark expired ones as failed."""
    result = await db.execute(
        select(TrainingJob).where(TrainingJob.status.in_(ACTIVE_JOB_STATUSES)).order_by(TrainingJob.created_at.desc())
    )
    jobs = result.scalars().all()
    if not jobs:
        return None, None

    now = datetime.now(UTC)
    dirty = False

    for job in jobs:
        state = await _read_redis_job_state(redis, job.job_id)
        if state is not None:
            redis_status = state.get("status")
            job.stage = state.get("stage") or job.stage
            job.progress = _coerce_progress(state.get("progress"), fallback=job.progress or 0)
            job.rows = state.get("rows") or job.rows
            job.current_model = state.get("current_model") or job.current_model
            job.current_model_index = state.get("current_model_index") or job.current_model_index
            job.total_models = state.get("total_models") or job.total_models
            if state.get("current_model_progress") is not None:
                job.current_model_progress = _coerce_progress(
                    state.get("current_model_progress"),
                    fallback=job.current_model_progress or 0,
                )
            job.fitted_trees = state.get("fitted_trees") or job.fitted_trees
            job.total_trees = state.get("total_trees") or job.total_trees
            job.elapsed_sec = state.get("elapsed_sec") or job.elapsed_sec
            job.eta_sec = state.get("eta_sec") or job.eta_sec
            job.error = state.get("error") or job.error
            dirty = True

            if redis_status == "completed":
                job.status = JobStatus.completed
                result_payload = state.get("result") or {}
                job.rows = result_payload.get("rows") or job.rows
                job.duration_sec = result_payload.get("duration_sec") or job.duration_sec
                job.current_model_progress = 100
                dirty = True
                continue

            if redis_status == "failed":
                job.status = JobStatus.failed
                dirty = True
                continue

            if dirty:
                await db.commit()
            return job, state

        if _job_is_stale(job, now):
            job.status = JobStatus.failed
            job.stage = "stale"
            job.error = "Training job state expired before completion."
            dirty = True
            continue

        if dirty:
            await db.commit()
        return job, None

    if dirty:
        await db.commit()
    return None, None


@router.post("/start", response_model=TrainStatusResponse)
async def start_training(
    req: TrainRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Start an async training job. Admin only."""
    csv_path = req.csv_path
    if not os.path.isabs(csv_path):
        csv_path = os.path.join(DATA_DIR, csv_path)
    csv_path = os.path.realpath(csv_path)
    if not csv_path.startswith(DATA_DIR + os.sep) and csv_path != DATA_DIR:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "CSV path is outside the allowed data directory")
    if os.path.islink(req.csv_path if os.path.isabs(req.csv_path) else os.path.join(DATA_DIR, req.csv_path)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Symbolic links are not allowed")
    if not os.path.exists(csv_path):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "CSV not found")

    settings = get_settings()
    redis = await create_pool(_parse_redis_url(settings.redis_url))
    try:
        active_job, active_state = await _reconcile_active_job(db, redis)
        if active_job is not None:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "detail": "A training job is already queued or running",
                    **_serialize_job(active_job, active_state).model_dump(),
                },
            )

        job_id = uuid.uuid4().hex[:16]

        # Record in DB
        job = TrainingJob(job_id=job_id, status=JobStatus.queued, csv_path=csv_path)
        db.add(job)
        await db.commit()

        # Enqueue ARQ task
        await redis.enqueue_job("run_training", job_id, csv_path)
    finally:
        await redis.close()

    return TrainStatusResponse(job_id=job_id, status="queued", progress=0)


@router.get("/active", response_model=TrainStatusResponse)
async def get_active_training(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Return the currently active queued/running training job, if any."""
    settings = get_settings()
    redis = await create_pool(_parse_redis_url(settings.redis_url))
    try:
        active_job, active_state = await _reconcile_active_job(db, redis)
    finally:
        await redis.close()

    if active_job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No active training job")

    return _serialize_job(active_job, active_state)


@router.get("/status/{job_id}", response_model=TrainStatusResponse)
async def get_training_status(
    job_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Get training job status from Redis."""
    settings = get_settings()
    redis = await create_pool(_parse_redis_url(settings.redis_url))
    try:
        data = await _read_redis_job_state(redis, job_id)
    finally:
        await redis.close()

    job_status = data.get("status", "unknown") if data else None

    # Invalidate caches when training completes
    if job_status == "completed":
        await invalidate_request_caches(request)
        result = await db.execute(select(TrainingJob).where(TrainingJob.job_id == job_id))
        job = result.scalar_one_or_none()
        if job is not None:
            return _serialize_job(job, data)

    if data is None:
        result = await db.execute(select(TrainingJob).where(TrainingJob.job_id == job_id))
        job = result.scalar_one_or_none()
        if job is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
        if job.status in ACTIVE_JOB_STATUSES and _job_is_stale(job, datetime.now(UTC)):
            job.status = JobStatus.failed
            job.stage = "stale"
            job.error = "Training job state expired before completion."
            await db.commit()
        return _serialize_job(job)

    payload = {key: value for key, value in data.items() if key != "progress"}
    return TrainStatusResponse(
        **payload,
        job_id=job_id,
        progress=_coerce_progress(data.get("progress")),
    )


@router.get("/jobs")
async def list_jobs(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """List all training jobs (most recent first)."""
    # Count total
    count_result = await db.execute(select(func.count(TrainingJob.id)))
    total = count_result.scalar() or 0
    pages = math.ceil(total / per_page) if total > 0 else 0

    offset = (page - 1) * per_page
    result = await db.execute(
        select(TrainingJob).order_by(TrainingJob.created_at.desc()).offset(offset).limit(per_page)
    )
    jobs = result.scalars().all()
    items = [
        TrainJobResponse(
            id=j.id,
            job_id=j.job_id,
            status=j.status.value if isinstance(j.status, JobStatus) else j.status,
            stage=j.stage,
            progress=j.progress,
            rows=j.rows,
            current_model=j.current_model,
            current_model_index=j.current_model_index,
            total_models=j.total_models,
            current_model_progress=j.current_model_progress,
            fitted_trees=j.fitted_trees,
            total_trees=j.total_trees,
            elapsed_sec=j.elapsed_sec,
            eta_sec=j.eta_sec,
            duration_sec=j.duration_sec,
            error=j.error,
            created_at=j.created_at.isoformat(),
            updated_at=j.updated_at.isoformat(),
        )
        for j in jobs
    ]
    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
    }


@router.delete("/jobs/clear", status_code=status.HTTP_200_OK)
async def clear_jobs(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    """Delete all training job records."""
    result = await db.execute(select(func.count(TrainingJob.id)))
    count = result.scalar() or 0
    await db.execute(delete(TrainingJob))
    await db.commit()
    return {"deleted": count}
