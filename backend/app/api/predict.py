"""Prediction routes — predict price, get history."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.prediction import PredictionLog
from app.models.user import User
from app.schemas.model import PredictRequest, PredictResponse
from app.services.model_service import predict_one

router = APIRouter(prefix="/predict", tags=["prediction"])


@router.post("", response_model=PredictResponse)
async def predict(
    req: PredictRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Predict property price."""
    features = req.model_dump(exclude_none=True)
    try:
        result = predict_one(features)
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))

    # Log prediction
    import json
    log = PredictionLog(
        payload_json=json.dumps(features),
        predicted_price_eur=result["predicted_price_eur"],
        used_features_json=json.dumps(result["features_used"]),
        user_id=user.id,
    )
    db.add(log)
    await db.commit()

    return PredictResponse(**result)


@router.get("/history")
async def prediction_history(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Get recent prediction history."""
    result = await db.execute(
        select(PredictionLog)
        .order_by(PredictionLog.created_at.desc())
        .limit(min(limit, 200))
    )
    logs = result.scalars().all()
    import json
    return [
        {
            "id": log.id,
            "payload": json.loads(log.payload_json),
            "predicted_price_eur": log.predicted_price_eur,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]
