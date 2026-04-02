"""Admin routes — user management (admin only)."""

import json
import math

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import require_admin
from app.models.dataset import DatasetFile
from app.models.model_run import ModelRun
from app.models.prediction import PredictionLog
from app.models.prepare_run import PrepareRun
from app.models.training_job import JobStatus, TrainingJob
from app.models.user import User, UserRole
from app.schemas.workbench import ActivityFeedItemResponse, AdminRunDetailResponse, AdminRunSummaryResponse
from app.utils.cache import cache_get, cache_set, invalidate_request_caches

router = APIRouter(prefix="/admin", tags=["admin"])


class UserListItem(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: str

    model_config = {"from_attributes": True}


class UpdateUserRequest(BaseModel):
    role: str | None = None
    is_active: bool | None = None


@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    offset = (page - 1) * per_page
    stmt = (
        select(User, func.count(User.id).over().label("total_count"))
        .order_by(User.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    rows = (await db.execute(stmt)).all()
    total = rows[0].total_count if rows else 0
    pages = math.ceil(total / per_page) if total > 0 else 0

    items = [
        UserListItem(
            id=u.User.id,
            email=u.User.email,
            full_name=u.User.full_name,
            role=u.User.role.value if isinstance(u.User.role, UserRole) else u.User.role,
            is_active=u.User.is_active,
            created_at=u.User.created_at.isoformat(),
        )
        for u in rows
    ]
    return {"items": items, "total": total, "page": page, "per_page": per_page, "pages": pages}


@router.patch("/users/{user_id}", response_model=UserListItem)
async def update_user(
    request: Request,
    user_id: int,
    body: UpdateUserRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    if user.id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot modify own account")

    if body.role is not None:
        try:
            user.role = UserRole(body.role)
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid role") from None

    if body.is_active is not None:
        user.is_active = body.is_active

    await db.commit()
    await db.refresh(user)
    await invalidate_request_caches(request, prefixes=("cache:admin:",))

    return UserListItem(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value if isinstance(user.role, UserRole) else user.role,
        is_active=user.is_active,
        created_at=user.created_at.isoformat(),
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    request: Request,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if user_id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot delete own account")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    await db.delete(user)
    await db.commit()
    await invalidate_request_caches(request, prefixes=("cache:admin:",))


@router.get("/stats")
async def admin_stats(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Platform usage statistics. Admin only."""
    response.headers["Cache-Control"] = "private, max-age=60"
    cache_key = "cache:admin:stats"
    cached = await cache_get(request, cache_key)
    if cached is not None:
        return cached

    stats_row = (
        await db.execute(
            select(
                select(func.count(User.id)).scalar_subquery().label("total_users"),
                select(func.count(User.id)).where(User.is_active == True).scalar_subquery().label("active_users"),  # noqa: E712
                select(func.count(PredictionLog.id)).scalar_subquery().label("total_predictions"),
                select(func.count(TrainingJob.id)).scalar_subquery().label("total_training_jobs"),
                select(func.count(TrainingJob.id))
                .where(TrainingJob.status == JobStatus.completed)
                .scalar_subquery()
                .label("completed_jobs"),
                select(func.count(DatasetFile.id)).scalar_subquery().label("total_datasets"),
            )
        )
    ).one()

    result = {
        "total_users": int(stats_row.total_users or 0),
        "active_users": int(stats_row.active_users or 0),
        "total_predictions": int(stats_row.total_predictions or 0),
        "total_training_jobs": int(stats_row.total_training_jobs or 0),
        "completed_jobs": int(stats_row.completed_jobs or 0),
        "total_datasets": int(stats_row.total_datasets or 0),
    }
    await cache_set(request, cache_key, result)
    return result


def _run_summary_from_prepare(run: PrepareRun) -> AdminRunSummaryResponse:
    pair_count = 0
    if run.source_pairs_json:
        parsed_pairs = json.loads(run.source_pairs_json)
        if isinstance(parsed_pairs, list):
            pair_count = len(parsed_pairs)
    return AdminRunSummaryResponse(
        id=run.job_id,
        run_type="prepare",
        status=run.status,
        stage=run.stage,
        progress=run.progress,
        title="ETN preparation run",
        summary=f"{pair_count} selected year pairs",
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


def _run_detail_from_prepare(run: PrepareRun) -> AdminRunDetailResponse:
    pairs = json.loads(run.source_pairs_json) if run.source_pairs_json else []
    enrichment_options = json.loads(run.enrichment_options_json) if run.enrichment_options_json else {}
    result_payload = json.loads(run.result_json) if run.result_json else {}
    timeline = [
        {"label": "Queued", "state": "done"},
        {
            "label": "Pair processing",
            "state": "done" if (run.pairs_completed or 0) >= (run.total_pairs or 1) else "active",
        },
        {"label": "Spatial enrichment", "state": "done" if run.spatial_phase else "pending"},
        {"label": "Completed", "state": "done" if run.status == "completed" else "pending"},
    ]
    metrics = [
        {"label": "Progress", "value": run.progress, "suffix": "%"},
        {"label": "Pairs completed", "value": run.pairs_completed or 0},
        {"label": "Rows", "value": run.rows or result_payload.get("rows") or 0},
    ]
    artifacts = []
    if result_payload.get("output_csv_path"):
        artifacts.append({"label": "Prepared dataset", "value": result_payload["output_csv_path"]})
    return AdminRunDetailResponse(
        id=run.job_id,
        run_type="prepare",
        status=run.status,
        stage=run.stage,
        progress=run.progress,
        title="ETN preparation run",
        summary=f"{len(pairs)} pair selections",
        created_at=run.created_at,
        updated_at=run.updated_at,
        timeline=timeline,
        metrics=metrics,
        artifacts=artifacts,
        context={
            "current_label": run.current_label,
            "spatial_phase": run.spatial_phase,
            "pairs": pairs,
            "enrichment_options": enrichment_options,
            "result": result_payload,
            "error": run.error,
        },
    )


def _run_summary_from_training(job: TrainingJob) -> AdminRunSummaryResponse:
    return AdminRunSummaryResponse(
        id=job.job_id,
        run_type="training",
        status=job.status.value if isinstance(job.status, JobStatus) else str(job.status),
        stage=job.stage,
        progress=job.progress,
        title="Model training job",
        summary=job.current_model or job.csv_path,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _run_detail_from_training(job: TrainingJob) -> AdminRunDetailResponse:
    timeline = [
        {"label": "Queued", "state": "done"},
        {
            "label": "Training",
            "state": "done" if job.status in {JobStatus.completed, JobStatus.failed} else "active",
        },
        {"label": "Completed", "state": "done" if job.status == JobStatus.completed else "pending"},
    ]
    metrics = [
        {"label": "Progress", "value": job.progress, "suffix": "%"},
        {"label": "Rows", "value": job.rows or 0},
        {"label": "Elapsed", "value": job.elapsed_sec or 0, "suffix": "s"},
        {"label": "ETA", "value": job.eta_sec or 0, "suffix": "s"},
    ]
    artifacts = []
    if job.csv_path:
        artifacts.append({"label": "Source CSV", "value": job.csv_path})
    return AdminRunDetailResponse(
        id=job.job_id,
        run_type="training",
        status=job.status.value if isinstance(job.status, JobStatus) else str(job.status),
        stage=job.stage,
        progress=job.progress,
        title="Model training job",
        summary=job.current_model or job.csv_path,
        created_at=job.created_at,
        updated_at=job.updated_at,
        timeline=timeline,
        metrics=metrics,
        artifacts=artifacts,
        context={
            "current_model": job.current_model,
            "current_model_index": job.current_model_index,
            "total_models": job.total_models,
            "current_model_progress": job.current_model_progress,
            "fitted_trees": job.fitted_trees,
            "total_trees": job.total_trees,
            "trees_per_sec": job.trees_per_sec,
            "duration_sec": job.duration_sec,
            "error": job.error,
        },
    )


@router.get("/activity", response_model=list[ActivityFeedItemResponse])
async def admin_activity(
    request: Request,
    response: Response,
    limit: int = Query(24, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    response.headers["Cache-Control"] = "private, max-age=60"
    cache_key = f"cache:admin:activity:{limit}"
    cached = await cache_get(request, cache_key)
    if cached is not None:
        return [ActivityFeedItemResponse(**item) for item in cached]

    items: list[ActivityFeedItemResponse] = []
    segment_limit = min(limit, 6)

    datasets = await db.execute(select(DatasetFile).order_by(DatasetFile.uploaded_at.desc()).limit(segment_limit))
    for row in datasets.scalars().all():
        items.append(
            ActivityFeedItemResponse(
                id=f"dataset:{row.id}",
                category="dataset",
                title="Dataset uploaded",
                body=row.original_name,
                link="/admin/podatki",
                scope="admin",
                created_at=row.uploaded_at,
                is_read=True,
                payload={"source_type": row.source_type, "row_count": row.row_count},
            )
        )

    prepares = await db.execute(select(PrepareRun).order_by(PrepareRun.updated_at.desc()).limit(segment_limit))
    for row in prepares.scalars().all():
        items.append(
            ActivityFeedItemResponse(
                id=f"prepare:{row.job_id}",
                category="prepare",
                title="Prepare run updated",
                body=row.stage or row.status,
                link="/admin/priprava",
                scope="admin",
                created_at=row.updated_at,
                is_read=True,
                payload={"progress": row.progress, "status": row.status},
            )
        )

    trainings = await db.execute(select(TrainingJob).order_by(TrainingJob.updated_at.desc()).limit(segment_limit))
    for row in trainings.scalars().all():
        items.append(
            ActivityFeedItemResponse(
                id=f"training:{row.job_id}",
                category="training",
                title="Training job updated",
                body=row.stage or row.current_model or str(row.status),
                link="/admin/model",
                scope="admin",
                created_at=row.updated_at,
                is_read=True,
                payload={"progress": row.progress, "status": row.status},
            )
        )

    model_runs = await db.execute(select(ModelRun).order_by(ModelRun.created_at.desc()).limit(segment_limit))
    for row in model_runs.scalars().all():
        items.append(
            ActivityFeedItemResponse(
                id=f"model-run:{row.id}",
                category="model_run",
                title="Model run recorded",
                body=f"R2 {row.r2:.3f}" if row.r2 is not None else (row.model_type or "Completed"),
                link="/admin/model",
                scope="admin",
                created_at=row.created_at,
                is_read=True,
                payload={"rows": row.rows, "mae": row.mae, "rmse": row.rmse},
            )
        )

    items.sort(key=lambda item: str(item.created_at), reverse=True)
    result = items[:limit]
    await cache_set(request, cache_key, [item.model_dump(mode="json") for item in result])
    return result


@router.get("/prepare-runs", response_model=list[AdminRunSummaryResponse])
async def list_prepare_runs(
    limit: int = Query(12, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(PrepareRun).order_by(PrepareRun.updated_at.desc()).limit(limit))
    return [_run_summary_from_prepare(item) for item in result.scalars().all()]


@router.get("/prepare-runs/{job_id}", response_model=AdminRunDetailResponse)
async def get_prepare_run_detail(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(PrepareRun).where(PrepareRun.job_id == job_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prepare run not found")
    return _run_detail_from_prepare(item)


@router.get("/training-runs", response_model=list[AdminRunSummaryResponse])
async def list_training_runs(
    limit: int = Query(12, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(TrainingJob).order_by(TrainingJob.updated_at.desc()).limit(limit))
    return [_run_summary_from_training(item) for item in result.scalars().all()]


@router.get("/training-runs/{job_id}", response_model=AdminRunDetailResponse)
async def get_training_run_detail(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(TrainingJob).where(TrainingJob.job_id == job_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Training run not found")
    return _run_detail_from_training(item)
