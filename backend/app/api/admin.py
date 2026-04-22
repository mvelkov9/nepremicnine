"""Admin routes — user management (admin only)."""

import json
import math
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select
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
DATA_DIR = os.path.realpath(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"))


class UserListItem(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: str
    last_login_at: str | None = None

    model_config = {"from_attributes": True}


class UpdateUserRequest(BaseModel):
    role: str | None = None
    is_active: bool | None = None


def _value_or(value, fallback):
    return fallback if value is None else value


def _relative_data_path(path: str | None) -> str | None:
    if not path or not isinstance(path, str):
        return path
    if not os.path.isabs(path):
        return path
    resolved = os.path.realpath(path)
    if resolved.startswith(DATA_DIR + os.sep) or resolved == DATA_DIR:
        return os.path.relpath(resolved, DATA_DIR).replace("\\", "/")
    return path


def _normalize_data_paths(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _normalize_data_paths(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_data_paths(item) for item in value]
    if isinstance(value, str):
        return _relative_data_path(value)
    return value


@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    search: str | None = Query(None),
    role: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    sort: str = Query("created_at"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    offset = (page - 1) * per_page
    stmt = select(User, func.count(User.id).over().label("total_count"))

    normalized_search = (search or "").strip()
    if normalized_search:
        pattern = f"%{normalized_search.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(func.coalesce(User.full_name, "")).like(pattern),
                func.lower(func.coalesce(User.email, "")).like(pattern),
            )
        )

    normalized_role = (role or "").strip().lower()
    if normalized_role in {member.value for member in UserRole}:
        stmt = stmt.where(User.role == UserRole(normalized_role))

    normalized_status = (status_filter or "").strip().lower()
    if normalized_status == "active":
        stmt = stmt.where(User.is_active == True)  # noqa: E712
    elif normalized_status == "disabled":
        stmt = stmt.where(User.is_active == False)  # noqa: E712

    sort_columns = {
        "id": User.id,
        "full_name": User.full_name,
        "email": User.email,
        "role": User.role,
        "is_active": User.is_active,
        "created_at": User.created_at,
    }
    sort_column = sort_columns.get(sort, User.created_at)
    stmt = stmt.order_by(sort_column.asc() if order == "asc" else sort_column.desc())
    stmt = stmt.offset(offset).limit(per_page)
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
            last_login_at=u.User.last_login_at.isoformat() if u.User.last_login_at else None,
        )
        for u in rows
    ]
    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "page_size": per_page,
        "pages": pages,
        "filters": {
            "search": normalized_search or None,
            "role": normalized_role or None,
            "status": normalized_status or None,
        },
        "sort": sort if sort in sort_columns else "created_at",
        "order": order,
    }


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
        last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
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
        "disabled_users": max(int(stats_row.total_users or 0) - int(stats_row.active_users or 0), 0),
        "admin_users": int(
            (await db.execute(select(func.count(User.id)).where(User.role == UserRole.admin))).scalar_one() or 0
        ),
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
    pairs = _normalize_data_paths(json.loads(run.source_pairs_json)) if run.source_pairs_json else []
    enrichment_options = (
        _normalize_data_paths(json.loads(run.enrichment_options_json)) if run.enrichment_options_json else {}
    )
    result_payload = _normalize_data_paths(json.loads(run.result_json)) if run.result_json else {}
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
        {"label": "Pairs completed", "value": _value_or(run.pairs_completed, 0)},
        {"label": "Rows", "value": _value_or(run.rows, _value_or(result_payload.get("rows"), 0))},
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
    source_csv_path = _relative_data_path(job.csv_path)
    return AdminRunSummaryResponse(
        id=job.job_id,
        run_type="training",
        status=job.status.value if isinstance(job.status, JobStatus) else str(job.status),
        stage=job.stage,
        progress=job.progress,
        title="Model training job",
        summary=job.current_model or source_csv_path,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _run_detail_from_training(job: TrainingJob) -> AdminRunDetailResponse:
    source_csv_path = _relative_data_path(job.csv_path)
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
        {"label": "Rows", "value": _value_or(job.rows, 0)},
        {"label": "Elapsed", "value": _value_or(job.elapsed_sec, 0), "suffix": "s"},
        {"label": "ETA", "value": _value_or(job.eta_sec, 0), "suffix": "s"},
    ]
    artifacts = []
    if source_csv_path:
        artifacts.append({"label": "Source CSV", "value": source_csv_path})
    return AdminRunDetailResponse(
        id=job.job_id,
        run_type="training",
        status=job.status.value if isinstance(job.status, JobStatus) else str(job.status),
        stage=job.stage,
        progress=job.progress,
        title="Model training job",
        summary=job.current_model or source_csv_path,
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
    segment_limit = limit

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
