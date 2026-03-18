"""Prediction routes — predict price, get history, clear history."""

from __future__ import annotations

import json
import logging
import math

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user, require_admin
from app.models.prediction import PredictionLog
from app.models.user import User
from app.rate_limit import limiter
from app.schemas.model import PredictRequest, PredictResponse
from app.services.model_service import predict_one

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/predict", tags=["prediction"])


@router.post("", response_model=PredictResponse)
@limiter.limit("30/minute")
async def predict(
    request: Request,
    req: PredictRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Predict property price."""
    features = req.model_dump(exclude_none=True)
    try:
        result = predict_one(features)
    except RuntimeError as exc:
        logger.error("Prediction failed: %s", exc, exc_info=True)
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Prediction failed. Ensure a model has been trained."
        ) from exc

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
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get recent prediction history for the current user."""
    offset = (page - 1) * per_page

    # Single query: fetch rows AND total count via window function
    stmt = (
        select(PredictionLog, func.count(PredictionLog.id).over().label("total_count"))
        .where(PredictionLog.user_id == user.id)
        .order_by(PredictionLog.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    rows = (await db.execute(stmt)).all()
    total = rows[0].total_count if rows else 0
    pages = math.ceil(total / per_page) if total > 0 else 0

    items = [
        {
            "id": row.PredictionLog.id,
            "payload": json.loads(row.PredictionLog.payload_json),
            "predicted_price_eur": row.PredictionLog.predicted_price_eur,
            "created_at": row.PredictionLog.created_at.isoformat(),
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


@router.delete("/history/clear", status_code=status.HTTP_200_OK)
async def clear_history(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    """Delete all prediction history."""
    result = await db.execute(select(func.count(PredictionLog.id)))
    count = result.scalar() or 0
    await db.execute(delete(PredictionLog))
    await db.commit()
    return {"deleted": count}
