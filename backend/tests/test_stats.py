"""Stats endpoint tests.

The stats endpoints read from a CSV file on disk.  When the CSV is absent the
handlers return safe empty / zero-value responses — which is what we assert here.
"""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
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


# ── Enhanced stats & coordinate conversion ───────────────────────────────────


@pytest.mark.asyncio
async def test_overview_includes_enhanced_fields(client: AsyncClient, admin_headers: dict):
    """When data exists, stats overview should include min_price, max_price, std_price, year_built_min, year_built_max."""

    fake_df = pd.DataFrame(
        {
            "price_eur": [100_000, 200_000, 300_000],
            "size_m2": [50, 80, 120],
            "municipality": ["Ljubljana"] * 3,
            "property_type": ["Stanovanje"] * 3,
            "year_built": [1970, 1990, 2010],
        }
    )
    with patch("app.api.stats._load_df", return_value=fake_df):
        resp = await client.get("/api/stats/overview", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "min_price" in data
    assert "max_price" in data
    assert "std_price" in data
    assert "year_built_min" in data
    assert "year_built_max" in data
    assert data["min_price"] == 100_000.0
    assert data["max_price"] == 300_000.0
    assert data["year_built_min"] == 1970
    assert data["year_built_max"] == 2010


@pytest.mark.asyncio
async def test_map_transactions_returns_wgs84_coordinates(client: AsyncClient, admin_headers: dict):
    """Verify D96/TM coordinates are converted to WGS84 range (45-47 lat, 13-17 lon)."""

    fake_df = pd.DataFrame(
        {
            "price_eur": [200_000.0],
            "size_m2": [75.0],
            "municipality": ["Ljubljana"],
            "property_type": ["Stanovanje"],
            "rooms": [3.0],
            "latitude": [100_000.0],  # D96/TM northing
            "longitude": [460_000.0],  # D96/TM easting
            "source_label": ["2024"],
        }
    )
    with patch("app.api.stats._load_df", return_value=fake_df):
        resp = await client.get("/api/stats/map-transactions", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    tx = data["transactions"][0]
    assert 45.0 <= tx["lat"] <= 47.0, f"lat {tx['lat']} not in WGS84 range"
    assert 13.0 <= tx["lon"] <= 17.0, f"lon {tx['lon']} not in WGS84 range"
