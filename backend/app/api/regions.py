"""Region and municipality reference data routes."""

from collections import Counter

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.region import RegionLookup
from app.models.user import User
from app.schemas.region import RegionListResponse, RegionLookupResponse
from app.services.regions_service import CANONICAL_REGION_ROWS
from app.utils.cache import cache_get, cache_set
from app.utils.slovenian_labels import (
    format_municipality_label,
    format_region_label,
    is_unknown_label,
    labels_match,
)

router = APIRouter(tags=["regions"])


def _canonical_region_pair(municipality: object | None, region: object | None) -> tuple[str, str] | None:
    canonical_municipality = format_municipality_label(municipality)
    canonical_region = format_region_label(region)
    if canonical_municipality is None or canonical_region is None:
        return None
    return canonical_region, canonical_municipality


def _canonical_pairs_from_rows(rows: list[object]) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    pairs: list[tuple[str, str]] = []
    for row in rows:
        municipality = getattr(row, "municipality", None)
        region = getattr(row, "region", None)
        pair = _canonical_region_pair(municipality, region)
        if pair is None or pair in seen:
            continue
        seen.add(pair)
        pairs.append(pair)
    return pairs


def _canonical_region_responses(rows: list[RegionLookup]) -> list[RegionLookupResponse]:
    seen: set[tuple[str, str]] = set()
    items: list[RegionLookupResponse] = []
    for row in rows:
        pair = _canonical_region_pair(row.obcina_naziv, row.regija_naziv)
        if pair is None or pair in seen:
            continue
        seen.add(pair)
        canonical_region, canonical_municipality = pair
        items.append(
            RegionLookupResponse(
                id=row.id,
                obcina_sifra=row.obcina_sifra,
                obcina_naziv=canonical_municipality,
                regija_naziv=canonical_region,
                vir=row.vir,
            )
        )
    return items


@router.get("/regions", response_model=RegionListResponse)
async def get_regions(
    request: Request,
    response: Response,
    stats: bool = Query(False, description="Include fallback data"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    response.headers["Cache-Control"] = "public, max-age=3600"
    cache_key = f"cache:regions:list:{'stats' if stats else 'default'}"
    cached = await cache_get(request, cache_key)
    if cached is not None:
        return RegionListResponse(**cached)

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
        result_payload = RegionListResponse(regions=fallback, total=len(fallback))
        await cache_set(request, cache_key, result_payload.model_dump(mode="json"))
        return result_payload

    canonical_rows = _canonical_region_responses(rows)
    result_payload = RegionListResponse(regions=canonical_rows, total=len(canonical_rows))
    await cache_set(request, cache_key, result_payload.model_dump(mode="json"))
    return result_payload


@router.get("/regions/stats")
async def get_region_stats(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    response.headers["Cache-Control"] = "public, max-age=3600"
    cache_key = "cache:regions:stats"
    cached = await cache_get(request, cache_key)
    if cached is not None:
        return cached

    result = await db.execute(
        select(
            RegionLookup.obcina_naziv.label("municipality"),
            RegionLookup.regija_naziv.label("region"),
        )
        .distinct()
        .order_by(RegionLookup.regija_naziv, RegionLookup.obcina_naziv)
    )
    rows = result.all()
    if not rows:
        # Return from fallback
        counts = Counter(str(row["regija_naziv"]) for row in CANONICAL_REGION_ROWS)
        payload = [{"region": r, "municipality_count": c} for r, c in sorted(counts.items())]
        await cache_set(request, cache_key, payload)
        return payload

    canonical_pairs = _canonical_pairs_from_rows(rows)
    counts = Counter(region for region, _municipality in canonical_pairs)
    payload = [{"region": region, "municipality_count": count} for region, count in sorted(counts.items())]
    await cache_set(request, cache_key, payload)
    return payload


@router.get("/regions/municipalities")
@router.get("/municipalities")
async def get_municipalities(
    request: Request,
    response: Response,
    region: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    response.headers["Cache-Control"] = "public, max-age=3600"
    cache_key = f"cache:regions:municipalities:{region or 'all'}"
    cached = await cache_get(request, cache_key)
    if cached is not None:
        return cached

    query = (
        select(
            RegionLookup.obcina_naziv.label("municipality"),
            RegionLookup.regija_naziv.label("region"),
        )
        .distinct()
        .order_by(RegionLookup.obcina_naziv, RegionLookup.regija_naziv)
    )

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
        await cache_set(request, cache_key, items)
        return items

    items = [
        {"municipality": municipality, "region": region}
        for region, municipality in sorted(
            _canonical_pairs_from_rows([row for row in rows if not is_unknown_label(row.municipality)]),
            key=lambda item: (item[1], item[0]),
        )
    ]
    if region:
        items = [item for item in items if labels_match(item["region"], region)]
    await cache_set(request, cache_key, items)
    return items
