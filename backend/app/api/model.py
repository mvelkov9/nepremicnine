"""Model info routes — current model metadata, feature importance, diagnostics, runs."""

from __future__ import annotations

import json
import logging
import math
import os

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
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
DATA_DIR = os.path.realpath(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"))


def _relative_data_path(path: str | None) -> str | None:
    if not path:
        return None
    resolved = os.path.realpath(path)
    if resolved.startswith(DATA_DIR + os.sep) or resolved == DATA_DIR:
        return os.path.relpath(resolved, DATA_DIR).replace("\\", "/")
    return path


@router.get("/info", response_model=ModelInfoResponse)
async def model_info(request: Request, response: Response, _user: User = Depends(get_current_user)):
    """Get current trained model metadata."""
    response.headers["Cache-Control"] = "private, max-age=60"

    cache_key = "cache:model:info"
    cached = await cache_get(request, cache_key)
    if cached is not None:
        return ModelInfoResponse(**cached)

    info = get_model_info()
    if info is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No trained model found")
    result = ModelInfoResponse(**{**info, "source_csv_path": _relative_data_path(info.get("csv_path"))})
    await cache_set(request, cache_key, result.model_dump())
    return result


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
        "ev_baseline_metrics": info.get("ev_baseline_metrics"),
        "variant_matrix": info.get("variant_matrix"),
        "variant_benchmarks": info.get("variant_benchmarks"),
        "per_type_metrics": info.get("per_type_metrics", {}),
        "per_type_features": info.get("per_type_features", {}),
        "per_region_metrics": info.get("per_region_metrics", {}),
        "per_type_count": info.get("per_type_count", 0),
        "type_models_trained": info.get("type_models_trained", []),
        "data_preparation": info.get("data_preparation"),
        "segment_diagnostics": info.get("segment_diagnostics"),
    }


@router.get("/runs")
async def model_runs(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    """Get model training run history."""
    offset = (page - 1) * per_page
    stmt = (
        select(ModelRun, func.count(ModelRun.id).over().label("total_count"))
        .order_by(ModelRun.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    rows = (await db.execute(stmt)).all()
    total = rows[0].total_count if rows else 0
    pages = math.ceil(total / per_page) if total > 0 else 0

    items = [
        {
            "id": row.ModelRun.id,
            "source_csv_path": _relative_data_path(row.ModelRun.source_csv_path),
            "rows": row.ModelRun.rows,
            "mae": row.ModelRun.mae,
            "rmse": row.ModelRun.rmse,
            "r2": row.ModelRun.r2,
            "mape": row.ModelRun.mape,
            "median_ae": row.ModelRun.median_ae,
            "duration_sec": row.ModelRun.duration_sec,
            "per_type_count": row.ModelRun.per_type_count,
            "model_type": row.ModelRun.model_type,
            "features": json.loads(row.ModelRun.features_json) if row.ModelRun.features_json else None,
            "importance": json.loads(row.ModelRun.importance_json) if row.ModelRun.importance_json else None,
            "combined_metrics": json.loads(row.ModelRun.combined_metrics_json)
            if row.ModelRun.combined_metrics_json
            else None,
            "created_at": row.ModelRun.created_at.isoformat(),
        }
        for row in rows
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
