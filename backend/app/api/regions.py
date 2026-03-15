"""Region and municipality reference data routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.region import RegionLookup
from app.models.user import User
from app.schemas.region import RegionListResponse, RegionLookupResponse
from app.services.regions_service import FALLBACK_REGIONS

router = APIRouter(tags=["regions"])


@router.get("/regions", response_model=RegionListResponse)
async def get_regions(
    stats: bool = Query(False, description="Include fallback data"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(RegionLookup).order_by(RegionLookup.regija_naziv, RegionLookup.obcina_naziv)
    )
    rows = result.scalars().all()

    # If DB is empty and stats requested, return fallback data
    if not rows and stats:
        fallback = [
            RegionLookupResponse(
                id=0,
                obcina_sifra=None,
                obcina_naziv=municipality,
                regija_naziv=region,
                vir="privzeto",
            )
            for municipality, region in FALLBACK_REGIONS.items()
        ]
        return RegionListResponse(regions=fallback, total=len(fallback))

    return RegionListResponse(
        regions=[RegionLookupResponse.model_validate(r) for r in rows],
        total=len(rows),
    )


@router.get("/regions/stats")
async def get_region_stats(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(
            RegionLookup.regija_naziv,
            func.count(distinct(RegionLookup.obcina_naziv)).label("municipality_count"),
        )
        .group_by(RegionLookup.regija_naziv)
        .order_by(RegionLookup.regija_naziv)
    )
    rows = result.all()
    if not rows:
        # Return from fallback
        from collections import Counter
        counts = Counter(FALLBACK_REGIONS.values())
        return [
            {"region": r, "municipality_count": c}
            for r, c in sorted(counts.items())
        ]
    return [
        {"region": row.regija_naziv, "municipality_count": row.municipality_count}
        for row in rows
    ]


@router.get("/municipalities")
async def get_municipalities(
    region: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    query = select(
        distinct(RegionLookup.obcina_naziv).label("municipality"),
        RegionLookup.regija_naziv.label("region"),
    ).order_by(RegionLookup.obcina_naziv)

    if region:
        query = query.where(RegionLookup.regija_naziv == region)

    result = await db.execute(query)
    rows = result.all()

    if not rows:
        # Return from fallback
        items = [
            {"municipality": m, "region": r}
            for m, r in sorted(FALLBACK_REGIONS.items())
        ]
        if region:
            items = [i for i in items if i["region"] == region]
        return items

    return [{"municipality": row.municipality, "region": row.region} for row in rows]
