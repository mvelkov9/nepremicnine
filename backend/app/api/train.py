"""Training routes — start training, check status, list jobs."""

from __future__ import annotations

import json
import os
import uuid

from arq import create_pool
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.dependencies.auth import get_current_user, require_admin
from app.models.training_job import JobStatus, TrainingJob
from app.models.user import User
from app.schemas.model import TrainJobResponse, TrainRequest, TrainStatusResponse
from app.tasks.training_worker import JOB_PREFIX, _parse_redis_url

router = APIRouter(prefix="/train", tags=["training"])

DATA_DIR = os.path.realpath(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"))


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
    if not os.path.exists(csv_path):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "CSV not found")

    job_id = uuid.uuid4().hex[:16]

    # Record in DB
    job = TrainingJob(job_id=job_id, status=JobStatus.queued, csv_path=csv_path)
    db.add(job)
    await db.commit()

    # Enqueue ARQ task
    settings = get_settings()
    redis = await create_pool(_parse_redis_url(settings.redis_url))
    try:
        await redis.enqueue_job("run_training", job_id, csv_path)
    finally:
        await redis.close()

    return TrainStatusResponse(job_id=job_id, status="queued", progress=0)


@router.get("/status/{job_id}", response_model=TrainStatusResponse)
async def get_training_status(
    job_id: str,
    _user: User = Depends(get_current_user),
):
    """Get training job status from Redis."""
    settings = get_settings()
    redis = await create_pool(_parse_redis_url(settings.redis_url))
    try:
        raw = await redis.get(f"{JOB_PREFIX}{job_id}")
    finally:
        await redis.close()

    if raw is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    data = json.loads(raw)
    return TrainStatusResponse(
        job_id=job_id,
        status=data.get("status", "unknown"),
        stage=data.get("stage"),
        progress=data.get("progress", 0),
        result=data.get("result"),
        error=data.get("error"),
    )


@router.get("/jobs", response_model=list[TrainJobResponse])
async def list_jobs(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """List all training jobs (most recent first)."""
    result = await db.execute(select(TrainingJob).order_by(TrainingJob.created_at.desc()).limit(50))
    jobs = result.scalars().all()
    return [
        TrainJobResponse(
            id=j.id,
            job_id=j.job_id,
            status=j.status.value if isinstance(j.status, JobStatus) else j.status,
            stage=j.stage,
            progress=j.progress,
            rows=j.rows,
            duration_sec=j.duration_sec,
            error=j.error,
            created_at=j.created_at.isoformat(),
            updated_at=j.updated_at.isoformat(),
        )
        for j in jobs
    ]


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
