"""Model info routes — current model metadata, feature importance, diagnostics, runs."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user, require_admin
from app.models.model_run import ModelRun
from app.models.user import User
from app.schemas.model import ModelInfoResponse
from app.services.model_service import get_model_info

router = APIRouter(prefix="/model", tags=["model"])


@router.get("/info", response_model=ModelInfoResponse)
async def model_info(_user: User = Depends(get_current_user)):
    """Get current trained model metadata."""
    info = get_model_info()
    if info is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No trained model found")
    return ModelInfoResponse(**info)


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
        "global_metrics": info.get("global_metrics"),
        "per_type_metrics": info.get("per_type_metrics", {}),
        "per_region_metrics": info.get("per_region_metrics", {}),
        "per_type_count": info.get("per_type_count", 0),
    }


@router.get("/runs")
async def model_runs(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Get model training run history."""
    result = await db.execute(select(ModelRun).order_by(ModelRun.created_at.desc()).limit(50))
    runs = result.scalars().all()
    return [
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


@router.delete("/runs/clear", status_code=status.HTTP_200_OK)
async def clear_model_runs(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    """Delete all model run records."""
    result = await db.execute(select(ModelRun))
    runs = result.scalars().all()
    count = len(runs)
    for r in runs:
        await db.delete(r)
    await db.commit()
    return {"deleted": count}
