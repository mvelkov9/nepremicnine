"""Stats endpoint tests.

The stats endpoints read from a CSV file on disk.  When the CSV is absent the
handlers return safe empty / zero-value responses — which is what we assert here.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

# ── GET /api/stats/overview ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_overview_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/stats/overview")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_overview_returns_json(client: AsyncClient, admin_headers: dict):
    resp = await client.get("/api/stats/overview", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_records" in data
    assert "avg_price" in data


@pytest.mark.asyncio
async def test_overview_with_property_type_filter(client: AsyncClient, admin_headers: dict):
    resp = await client.get("/api/stats/overview?property_type=Stanovanje", headers=admin_headers)
    assert resp.status_code == 200
    assert "total_records" in resp.json()


# ── GET /api/stats/regions ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_regions_stats_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/stats/regions")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_regions_stats_returns_json(client: AsyncClient, admin_headers: dict):
    resp = await client.get("/api/stats/regions", headers=admin_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ── GET /api/stats/price-distribution ────────────────────────────────────────


@pytest.mark.asyncio
async def test_price_distribution_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/stats/price-distribution")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_price_distribution_returns_json(client: AsyncClient, admin_headers: dict):
    resp = await client.get("/api/stats/price-distribution", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "bins" in data
    assert "counts" in data
    assert "bin_labels" in data


@pytest.mark.asyncio
async def test_price_distribution_custom_bins(client: AsyncClient, admin_headers: dict):
    resp = await client.get("/api/stats/price-distribution?bins=10", headers=admin_headers)
    assert resp.status_code == 200


# ── GET /api/stats/trend ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_trend_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/stats/trend")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_trend_returns_json(client: AsyncClient, admin_headers: dict):
    resp = await client.get("/api/stats/trend", headers=admin_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ── GET /api/stats/map-transactions ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_map_transactions_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/stats/map-transactions")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_map_transactions_returns_json(client: AsyncClient, admin_headers: dict):
    resp = await client.get("/api/stats/map-transactions", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "transactions" in data
    assert "count" in data


@pytest.mark.asyncio
async def test_map_transactions_with_filters(client: AsyncClient, admin_headers: dict):
    resp = await client.get(
        "/api/stats/map-transactions?property_type=Stanovanje&limit=100",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert "transactions" in resp.json()


# ── GET /api/stats/municipalities-by-region ──────────────────────────────────


@pytest.mark.asyncio
async def test_municipalities_by_region_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/stats/municipalities-by-region")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_municipalities_by_region_returns_json(client: AsyncClient, admin_headers: dict):
    resp = await client.get("/api/stats/municipalities-by-region", headers=admin_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)
