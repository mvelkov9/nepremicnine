"""Model info routes — current model metadata, feature importance."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import get_current_user
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
