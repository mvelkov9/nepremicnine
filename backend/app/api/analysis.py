"""Listing analysis routes — score listings against trained model."""

from __future__ import annotations

import logging
import math

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.listings_run import ListingsRun
from app.models.user import User
from app.rate_limit import limiter
from app.services.model_service import load_model, predict_one

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["analysis"])


class ListingItem(BaseModel):
    size_m2: float = Field(..., ge=1, le=10000)
    rooms: float | None = None
    year_built: int | None = None
    floor: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    municipality: str | None = None
    property_type: str = "stanovanje"
    asking_price: float = Field(..., ge=0)


class ScoreRequest(BaseModel):
    listings: list[ListingItem] = Field(..., min_length=1, max_length=500)
    threshold: float = Field(15.0, ge=0.0, le=100.0)


class ScoredListing(BaseModel):
    index: int
    asking_price: float
    predicted_price: float
    deviation_pct: float
    label: str
    size_m2: float | None = None
    rooms: float | None = None
    year_built: int | None = None
    floor: int | None = None
    municipality: str | None = None
    property_type: str | None = None


class ScoreResponse(BaseModel):
    total: int
    overpriced: int
    underpriced: int
    market_aligned: int
    listings: list[ScoredListing]


@router.post("/score", response_model=ScoreResponse)
@limiter.limit("10/minute")
async def score_listings(
    request: Request,
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
                size_m2=listing.size_m2,
                rooms=listing.rooms,
                year_built=listing.year_built,
                floor=listing.floor,
                municipality=listing.municipality,
                property_type=listing.property_type,
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


@router.get("/runs")
async def list_runs(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """List past analysis runs with pagination."""
    count_result = await db.execute(select(func.count(ListingsRun.id)))
    total = count_result.scalar() or 0
    pages = math.ceil(total / per_page) if total > 0 else 0

    offset = (page - 1) * per_page
    result = await db.execute(
        select(ListingsRun).order_by(ListingsRun.created_at.desc()).offset(offset).limit(per_page)
    )
    runs = result.scalars().all()
    items = [
        {
            "id": r.id,
            "threshold": r.threshold,
            "total_count": r.total_count,
            "overpriced_count": r.overpriced_count,
            "underpriced_count": r.underpriced_count,
            "market_aligned_count": r.market_aligned_count,
            "created_at": r.created_at.isoformat(),
        }
        for r in runs
    ]
    return {"items": items, "total": total, "page": page, "per_page": per_page, "pages": pages}
