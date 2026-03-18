"""Region and municipality reference data routes."""

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.region import RegionLookup
from app.models.user import User
from app.schemas.region import RegionListResponse, RegionLookupResponse
from app.services.regions_service import CANONICAL_REGION_ROWS
from app.utils.slovenian_labels import (
    format_municipality_label,
    format_region_label,
    is_unknown_label,
    labels_match,
)

router = APIRouter(tags=["regions"])


@router.get("/regions", response_model=RegionListResponse)
async def get_regions(
    response: Response,
    stats: bool = Query(False, description="Include fallback data"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    response.headers["Cache-Control"] = "public, max-age=3600"
    result = await db.execute(select(RegionLookup).order_by(RegionLookup.regija_naziv, RegionLookup.obcina_naziv))
    rows = result.scalars().all()

    # If DB is empty and stats requested, return fallback data
    if not rows and stats:
        fallback = [
            RegionLookupResponse(
                id=0,
                obcina_sifra=row["obcina_sifra"],
                obcina_naziv=str(row["obcina_naziv"]),
                regija_naziv=str(row["regija_naziv"]),
                vir=str(row["vir"]),
            )
            for row in CANONICAL_REGION_ROWS
        ]
        return RegionListResponse(regions=fallback, total=len(fallback))

    return RegionListResponse(
        regions=[
            RegionLookupResponse(
                id=row.id,
                obcina_sifra=row.obcina_sifra,
                obcina_naziv=format_municipality_label(row.obcina_naziv) or row.obcina_naziv,
                regija_naziv=format_region_label(row.regija_naziv) or row.regija_naziv,
                vir=row.vir,
            )
            for row in rows
        ],
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

        counts = Counter(str(row["regija_naziv"]) for row in CANONICAL_REGION_ROWS)
        return [{"region": r, "municipality_count": c} for r, c in sorted(counts.items())]
    return [
        {
            "region": format_region_label(row.regija_naziv) or row.regija_naziv,
            "municipality_count": row.municipality_count,
        }
        for row in rows
    ]


@router.get("/regions/municipalities")
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

    result = await db.execute(query)
    rows = result.all()

    if not rows:
        # Return from fallback
        items = [
            {
                "municipality": str(row["obcina_naziv"]),
                "region": str(row["regija_naziv"]),
            }
            for row in CANONICAL_REGION_ROWS
        ]
        if region:
            items = [item for item in items if labels_match(item["region"], region)]
        return items

    items = [
        {
            "municipality": format_municipality_label(row.municipality) or row.municipality,
            "region": format_region_label(row.region) or row.region,
        }
        for row in rows
        if not is_unknown_label(row.municipality)
    ]
    if region:
        items = [item for item in items if labels_match(item["region"], region)]
    return items
