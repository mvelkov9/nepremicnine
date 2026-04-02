"""Shell activity and notification routes."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.activity import ActivityEvent
from app.models.dataset import DatasetFile
from app.models.listings_run import ListingsRun
from app.models.model_run import ModelRun
from app.models.prediction import PredictionLog
from app.models.prepare_run import PrepareRun
from app.models.training_job import TrainingJob
from app.models.user import User
from app.schemas.workbench import ActivityFeedItemResponse, MarkActivityReadResponse
from app.utils.cache import cache_get, cache_set, invalidate_request_caches

router = APIRouter(prefix="/activity", tags=["activity"])


def _activity_from_model(
    *,
    item_id: str,
    category: str,
    title: str,
    body: str | None,
    link: str | None,
    scope: str,
    created_at,
    payload: dict | None = None,
    is_read: bool = True,
) -> ActivityFeedItemResponse:
    return ActivityFeedItemResponse(
        id=item_id,
        category=category,
        title=title,
        body=body,
        link=link,
        scope=scope,
        is_read=is_read,
        created_at=created_at,
        payload=payload or {},
    )


@router.get("/feed", response_model=list[ActivityFeedItemResponse])
async def activity_feed(
    request: Request,
    response: Response,
    limit: int = Query(24, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    response.headers["Cache-Control"] = "private, max-age=60"
    cache_key = f"cache:activity:feed:{user.id}:{limit}"
    cached = await cache_get(request, cache_key)
    if cached is not None:
        return [ActivityFeedItemResponse(**item) for item in cached]

    items: list[ActivityFeedItemResponse] = []

    event_rows = await db.execute(
        select(ActivityEvent)
        .where(ActivityEvent.user_id == user.id)
        .order_by(ActivityEvent.created_at.desc())
        .limit(min(limit, 15))
    )
    for event in event_rows.scalars().all():
        items.append(
            _activity_from_model(
                item_id=f"event:{event.id}",
                category=event.category,
                title=event.title,
                body=event.body,
                link=event.link,
                scope=event.scope,
                created_at=event.created_at,
                payload=json.loads(event.payload_json) if event.payload_json else {},
                is_read=event.is_read,
            )
        )

    prediction_rows = await db.execute(
        select(PredictionLog)
        .where(PredictionLog.user_id == user.id)
        .order_by(PredictionLog.created_at.desc())
        .limit(min(limit, 4))
    )
    for row in prediction_rows.scalars().all():
        payload = json.loads(row.payload_json) if row.payload_json else {}
        items.append(
            _activity_from_model(
                item_id=f"prediction:{row.id}",
                category="prediction",
                title="Saved valuation context",
                body=str(payload.get("municipality") or payload.get("naselje") or "Prediction run"),
                link="/napoved",
                scope="viewer",
                created_at=row.created_at,
                payload=payload,
            )
        )

    analysis_rows = await db.execute(select(ListingsRun).order_by(ListingsRun.created_at.desc()).limit(min(limit, 4)))
    for row in analysis_rows.scalars().all():
        items.append(
            _activity_from_model(
                item_id=f"analysis:{row.id}",
                category="analysis",
                title="Analysis run completed",
                body=f"{row.total_count} listings scored",
                link="/analiza",
                scope="viewer",
                created_at=row.created_at,
                payload={"threshold": row.threshold},
            )
        )

    if user.role.value == "admin":
        prepare_rows = await db.execute(select(PrepareRun).order_by(PrepareRun.created_at.desc()).limit(min(limit, 4)))
        for row in prepare_rows.scalars().all():
            items.append(
                _activity_from_model(
                    item_id=f"prepare:{row.job_id}",
                    category="prepare",
                    title="Prepare run updated",
                    body=row.stage or row.status,
                    link="/admin/priprava",
                    scope="admin",
                    created_at=row.updated_at,
                    payload={"status": row.status, "progress": row.progress},
                )
            )

        training_rows = await db.execute(
            select(TrainingJob).order_by(TrainingJob.created_at.desc()).limit(min(limit, 4))
        )
        for row in training_rows.scalars().all():
            items.append(
                _activity_from_model(
                    item_id=f"train:{row.job_id}",
                    category="training",
                    title="Training job updated",
                    body=row.stage or row.status,
                    link="/admin/model",
                    scope="admin",
                    created_at=row.updated_at,
                    payload={"status": row.status, "progress": row.progress},
                )
            )

        dataset_rows = await db.execute(
            select(DatasetFile).order_by(DatasetFile.uploaded_at.desc()).limit(min(limit, 4))
        )
        for row in dataset_rows.scalars().all():
            items.append(
                _activity_from_model(
                    item_id=f"dataset:{row.id}",
                    category="dataset",
                    title="Dataset library updated",
                    body=row.original_name,
                    link="/admin/podatki",
                    scope="admin",
                    created_at=row.uploaded_at,
                    payload={"source_type": row.source_type},
                )
            )

        run_rows = await db.execute(select(ModelRun).order_by(ModelRun.created_at.desc()).limit(min(limit, 4)))
        for row in run_rows.scalars().all():
            items.append(
                _activity_from_model(
                    item_id=f"model-run:{row.id}",
                    category="model_run",
                    title="Model run recorded",
                    body=f"R2 {row.r2:.3f}" if row.r2 is not None else row.model_type,
                    link="/admin/model",
                    scope="admin",
                    created_at=row.created_at,
                    payload={"rows": row.rows, "mae": row.mae, "rmse": row.rmse},
                )
            )

    items.sort(key=lambda item: str(item.created_at), reverse=True)
    result = items[:limit]
    await cache_set(request, cache_key, [item.model_dump(mode="json") for item in result])
    return result


@router.get("/unread")
async def activity_unread(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    total = await db.execute(
        select(func.count(ActivityEvent.id)).where(ActivityEvent.user_id == user.id, ActivityEvent.is_read == False)  # noqa: E712
    )
    return {"unread": int(total.scalar() or 0)}


@router.post("/{activity_id}/read", response_model=MarkActivityReadResponse)
async def mark_activity_read(
    request: Request,
    activity_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = await db.get(ActivityEvent, activity_id)
    if item is None or item.user_id != user.id:
        raise HTTPException(status_code=404, detail="Activity not found")
    item.is_read = True
    await db.commit()

    unread = await db.execute(
        select(func.count(ActivityEvent.id)).where(ActivityEvent.user_id == user.id, ActivityEvent.is_read == False)  # noqa: E712
    )
    await invalidate_request_caches(request, prefixes=("cache:activity:",))
    return MarkActivityReadResponse(ok=True, unread=int(unread.scalar() or 0))
