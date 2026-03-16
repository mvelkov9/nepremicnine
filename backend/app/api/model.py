"""Model info routes — current model metadata, feature importance, diagnostics, runs."""

from __future__ import annotations

import json
import logging
import math

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user, require_admin
from app.models.model_run import ModelRun
from app.models.user import User
from app.schemas.model import ModelInfoResponse
from app.services.model_service import get_model_info
from app.utils.cache import cache_get, cache_set

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/model", tags=["model"])


@router.get("/info", response_model=ModelInfoResponse)
async def model_info(request: Request, _user: User = Depends(get_current_user)):
    """Get current trained model metadata."""
    cache_key = "cache:model:info"
    cached = await cache_get(request, cache_key)
    if cached is not None:
        return ModelInfoResponse(**cached)

    info = get_model_info()
    if info is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No trained model found")
    response = ModelInfoResponse(**info)
    await cache_set(request, cache_key, response.model_dump())
    return response


@router.get("/importance")
async def feature_importance(_user: User = Depends(get_current_user)):
    """Get feature importance from the global model."""
    info = get_model_info()
    if info is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No trained model found")

    importance = info.get("global_importance", {})
    labels = info.get("feature_labels", {})

    items = sorted(importance.items(), key=lambda x: x[1], reverse=True)
    return [
        {
            "feature": feat,
            "label": labels.get(feat.split("__")[-1], feat),
            "importance": round(val, 4),
        }
        for feat, val in items
    ]


@router.get("/diagnostics")
async def model_diagnostics(_user: User = Depends(get_current_user)):
    """Get per-type and per-region model diagnostics."""
    info = get_model_info()
    if info is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No trained model found")

    return {
        "version": info.get("version"),
        "trained_at": info.get("trained_at"),
        "rows": info.get("rows"),
        "train_rows": info.get("train_rows"),
        "test_rows": info.get("test_rows"),
        "model_type": info.get("model_type", "HistGradientBoostingRegressor"),
        "used_features": info.get("used_features", []),
        "global_metrics": info.get("global_metrics"),
        "combined_metrics": info.get("combined_metrics"),
        "per_type_metrics": info.get("per_type_metrics", {}),
        "per_region_metrics": info.get("per_region_metrics", {}),
        "per_type_count": info.get("per_type_count", 0),
        "type_models_trained": info.get("type_models_trained", []),
    }


@router.get("/runs")
async def model_runs(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Get model training run history."""
    # Count total
    count_result = await db.execute(select(func.count(ModelRun.id)))
    total = count_result.scalar() or 0
    pages = math.ceil(total / per_page) if total > 0 else 0

    offset = (page - 1) * per_page
    result = await db.execute(select(ModelRun).order_by(ModelRun.created_at.desc()).offset(offset).limit(per_page))
    runs = result.scalars().all()
    items = [
        {
            "id": r.id,
            "source_csv_path": r.source_csv_path,
            "rows": r.rows,
            "mae": r.mae,
            "rmse": r.rmse,
            "r2": r.r2,
            "features": json.loads(r.features_json) if r.features_json else None,
            "importance": json.loads(r.importance_json) if r.importance_json else None,
            "created_at": r.created_at.isoformat(),
        }
        for r in runs
    ]
    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
    }


@router.delete("/runs/clear", status_code=status.HTTP_200_OK)
async def clear_model_runs(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    """Delete all model run records."""
    result = await db.execute(select(func.count(ModelRun.id)))
    count = result.scalar() or 0
    await db.execute(delete(ModelRun))
    await db.commit()
    return {"deleted": count}
