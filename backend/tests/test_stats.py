"""Stats endpoint tests.

The stats endpoints read from a CSV file on disk.  When the CSV is absent the
handlers return safe empty / zero-value responses — which is what we assert here.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest
from httpx import AsyncClient


def _build_market_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "price_eur": [
                210_000,
                245_000,
                265_000,
                590_000,
                150_000,
                165_000,
                180_000,
                172_000,
                205_000,
            ],
            "size_m2": [62, 71, 74, 180, 58, 63, 67, 59, 86],
            "uporabna_povrsina": [60, 69, 72, 170, 55, 60, 64, 56, 82],
            "municipality": [
                "Ljubljana",
                "Ljubljana",
                "Ljubljana",
                "Ljubljana",
                "Maribor",
                "Maribor",
                "Škofja Loka",
                "Škofja Loka",
                "Kranj",
            ],
            "property_type": [
                "stanovanje",
                "stanovanje",
                "stanovanje",
                "hisa",
                "stanovanje",
                "stanovanje",
                "stanovanje",
                "stanovanje",
                "stanovanje",
            ],
            "year_built": [1998, 2004, 2011, 1987, 1979, 1982, 2006, 2008, 1995],
            "source_label": ["2022", "2023", "2024", "2024", "2023", "2024", "2023", "2024", "2024"],
            "statistical_region": [
                "osrednjeslovenska",
                "osrednjeslovenska",
                "osrednjeslovenska",
                "osrednjeslovenska",
                "podravska",
                "podravska",
                "gorenjska",
                "gorenjska",
                "gorenjska",
            ],
            "latitude": [100_000.0] * 9,
            "longitude": [460_000.0] * 9,
        }
    )


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
    assert "meta" in data


@pytest.mark.asyncio
async def test_map_transactions_with_filters(client: AsyncClient, admin_headers: dict):
    resp = await client.get(
        "/api/stats/map-transactions?property_type=Stanovanje&limit=100",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert "transactions" in resp.json()


@pytest.mark.asyncio
async def test_map_transactions_returns_reason_for_empty_filter_match(client: AsyncClient, admin_headers: dict):
    fake_df = _build_market_df()
    with patch("app.api.stats._load_df", return_value=fake_df):
        resp = await client.get(
            "/api/stats/map-transactions?municipality=Neobstojeca",
            headers=admin_headers,
        )
    assert resp.status_code == 200
    assert resp.json()["meta"]["reason"] == "no_matches"


# ── GET /api/stats/map-overview ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_map_overview_returns_municipality_markers(client: AsyncClient, admin_headers: dict):
    fake_df = _build_market_df()
    with patch("app.api.stats._load_df", return_value=fake_df):
        resp = await client.get("/api/stats/map-overview", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 1
    assert data["municipalities"][0]["municipality"] == "Ljubljana"
    assert data["municipalities"][0]["lat"] is not None
    assert data["meta"]["reason"] is None


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


@pytest.mark.asyncio
async def test_municipalities_by_region_filters_single_region(client: AsyncClient, admin_headers: dict):
    fake_df = _build_market_df()
    with patch("app.api.stats._load_df", return_value=fake_df):
        resp = await client.get(
            "/api/stats/municipalities-by-region?region=gorenjska",
            headers=admin_headers,
        )
    assert resp.status_code == 200
    assert resp.json() == [{"municipality": "Kranj"}, {"municipality": "Škofja Loka"}]


# ── GET /api/stats/market-home ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_market_home_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/stats/market-home")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_market_home_returns_rankings_and_latest_sales(client: AsyncClient, admin_headers: dict):
    fake_df = _build_market_df()
    with patch("app.api.stats._load_df", return_value=fake_df):
        resp = await client.get("/api/stats/market-home", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["headline"]["total_records"] == len(fake_df)
    assert data["largest_markets"][0]["municipality"] == "Ljubljana"
    assert data["latest_sales"]
    assert any(item["year"] == "2024" for item in data["year_coverage"])


@pytest.mark.asyncio
async def test_market_home_formats_ascii_labels_for_display(client: AsyncClient, admin_headers: dict):
    fake_df = _build_market_df().copy()
    fake_df["municipality"] = [
        "ljubljana",
        "ljubljana",
        "ljubljana",
        "ljubljana",
        "maribor",
        "maribor",
        "skofja loka",
        "skofja loka",
        "kranj",
    ]
    fake_df["statistical_region"] = [
        "osrednjeslovenska",
        "osrednjeslovenska",
        "osrednjeslovenska",
        "osrednjeslovenska",
        "podravska",
        "podravska",
        "goriska",
        "goriska",
        "obalno-kraska",
    ]
    with (
        patch("app.api.stats._load_df", return_value=fake_df),
        patch.dict("app.api.stats._PREPARED_DF_CACHE", {"mtime": None, "df": None}),
        patch.dict("app.api.stats._RAW_DF_CACHE", {"mtime": None, "df": None}),
    ):
        resp = await client.get("/api/stats/market-home", headers=admin_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["largest_markets"][0]["municipality"] == "Ljubljana"
    assert {item["region"] for item in data["region_snapshot"]} >= {"Osrednjeslovenska", "Podravska", "Goriška"}


@pytest.mark.asyncio
async def test_market_home_uses_cache_when_available(client: AsyncClient, admin_headers: dict):
    cached = {
        "headline": {"total_records": 7},
        "largest_markets": [],
        "price_leaders": [],
        "region_snapshot": [],
        "latest_sales": [],
        "year_coverage": [],
        "property_type_mix": [],
    }
    with (
        patch("app.api.stats.cache_get", new=AsyncMock(return_value=cached)),
        patch("app.api.stats._load_df") as mocked_load_df,
    ):
        resp = await client.get("/api/stats/market-home", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json() == cached
    mocked_load_df.assert_not_called()


# ── GET /api/stats/municipality/{slug} ──────────────────────────────────────


@pytest.mark.asyncio
async def test_municipality_detail_normalizes_slug(client: AsyncClient, admin_headers: dict):
    fake_df = _build_market_df()
    with patch("app.api.stats._load_df", return_value=fake_df):
        resp = await client.get("/api/stats/municipality/skofja-loka", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["municipality"] == "Škofja Loka"
    assert data["slug"] == "skofja-loka"
    assert data["overview"]["count"] == 2
    assert data["recent_transactions"]


@pytest.mark.asyncio
async def test_municipality_detail_returns_404_for_unknown_slug(client: AsyncClient, admin_headers: dict):
    fake_df = _build_market_df()
    with patch("app.api.stats._load_df", return_value=fake_df):
        resp = await client.get("/api/stats/municipality/not-real", headers=admin_headers)
    assert resp.status_code == 404


# ── GET /api/stats/comparables ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_comparables_rank_same_municipality_first(client: AsyncClient, admin_headers: dict):
    fake_df = _build_market_df()
    with patch("app.api.stats._load_df", return_value=fake_df):
        resp = await client.get(
            "/api/stats/comparables?municipality=Ljubljana&property_type=stanovanje&size_m2=70&year_built=2006&price_eur=250000&limit=5",
            headers=admin_headers,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["target"]["municipality"] == "Ljubljana"
    assert data["summary"]["count"] > 0
    assert data["items"][0]["municipality"] == "Ljubljana"
    assert data["items"][0]["similarity_score"] is not None


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
    with (
        patch("app.api.stats._load_df", return_value=fake_df),
        patch.dict("app.api.stats._PREPARED_DF_CACHE", {"mtime": None, "df": None}),
        patch.dict("app.api.stats._RAW_DF_CACHE", {"mtime": None, "df": None}),
    ):
        resp = await client.get("/api/stats/map-transactions", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    tx = data["transactions"][0]
    assert 45.0 <= tx["lat"] <= 47.0, f"lat {tx['lat']} not in WGS84 range"
    assert 13.0 <= tx["lon"] <= 17.0, f"lon {tx['lon']} not in WGS84 range"
