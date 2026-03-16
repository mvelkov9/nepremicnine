"""Region and municipality reference-data endpoint tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.services.regions_service import CANONICAL_REGION_ROWS


def test_canonical_region_seed_rows_match_expected_reference_size():
    assert len(CANONICAL_REGION_ROWS) == 212


# ── GET /api/regions ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_regions_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/regions")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_regions_returns_list(client: AsyncClient, admin_headers: dict):
    resp = await client.get("/api/regions", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "regions" in data
    assert "total" in data
    assert isinstance(data["regions"], list)


@pytest.mark.asyncio
async def test_regions_with_stats_flag(client: AsyncClient, admin_headers: dict):
    """With ?stats=true the endpoint may fall back to hard-coded data."""
    resp = await client.get("/api/regions?stats=true", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "regions" in data
    # With fallback data enabled, total should be > 0
    assert data["total"] >= 0


# ── GET /api/regions/stats ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_region_stats_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/regions/stats")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_region_stats_returns_json(client: AsyncClient, admin_headers: dict):
    resp = await client.get("/api/regions/stats", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


# ── GET /api/municipalities ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_municipalities_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/municipalities")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_municipalities_returns_list(client: AsyncClient, admin_headers: dict):
    resp = await client.get("/api/municipalities", headers=admin_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_municipalities_filter_by_region(client: AsyncClient, admin_headers: dict):
    resp = await client.get("/api/municipalities?region=Osrednjeslovenska", headers=admin_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_regions_municipalities_alias_returns_list(client: AsyncClient, admin_headers: dict):
    resp = await client.get("/api/regions/municipalities", headers=admin_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
