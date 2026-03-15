"""Listing analysis routes — score listings against trained model."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.listings_run import ListingsRun
from app.models.user import User
from app.services.model_service import load_model, predict_one

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["analysis"])


class ListingItem(BaseModel):
    size_m2: float
    rooms: float | None = None
    year_built: int | None = None
    floor: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    municipality: str | None = None
    property_type: str = "stanovanje"
    asking_price: float


class ScoreRequest(BaseModel):
    listings: list[ListingItem]
    threshold: float = 15.0


class ScoredListing(BaseModel):
    index: int
    asking_price: float
    predicted_price: float
    deviation_pct: float
    label: str


class ScoreResponse(BaseModel):
    total: int
    overpriced: int
    underpriced: int
    market_aligned: int
    listings: list[ScoredListing]


@router.post("/score", response_model=ScoreResponse)
async def score_listings(
    req: ScoreRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    artifact = load_model()
    if artifact is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "No trained model. Train first.")

    scored = []
    overpriced = underpriced = market_aligned = 0

    for i, listing in enumerate(req.listings):
        features = listing.model_dump(exclude={"asking_price"}, exclude_none=True)
        try:
            result = predict_one(features)
            predicted = result["predicted_price_eur"]
        except (RuntimeError, ValueError):
            logger.warning("Prediction failed for listing %d, skipping", i, exc_info=True)
            continue

        deviation = ((listing.asking_price - predicted) / predicted) * 100 if predicted > 0 else 0

        if deviation > req.threshold:
            label = "overpriced"
            overpriced += 1
        elif deviation < -req.threshold:
            label = "underpriced"
            underpriced += 1
        else:
            label = "market_aligned"
            market_aligned += 1

        scored.append(
            ScoredListing(
                index=i,
                asking_price=listing.asking_price,
                predicted_price=round(predicted, 2),
                deviation_pct=round(deviation, 2),
                label=label,
            )
        )

    # Save run to DB
    run = ListingsRun(
        threshold=req.threshold,
        total_count=len(scored),
        overpriced_count=overpriced,
        underpriced_count=underpriced,
        market_aligned_count=market_aligned,
    )
    db.add(run)
    await db.commit()

    return ScoreResponse(
        total=len(scored),
        overpriced=overpriced,
        underpriced=underpriced,
        market_aligned=market_aligned,
        listings=scored,
    )
