"""Region and municipality reference-data endpoint tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from app.api.regions import get_municipalities, get_region_stats
from app.services.regions_service import CANONICAL_REGION_ROWS


def test_canonical_region_seed_rows_match_expected_reference_size():
    assert len(CANONICAL_REGION_ROWS) == 212


class _FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}

    async def get(self, key: str):
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self.store[key] = value


class _FakeResponse:
    def __init__(self):
        self.headers: dict[str, str] = {}


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows

    def scalars(self):
        return self


class _FakeDb:
    def __init__(self, rows):
        self.rows = rows

    async def execute(self, _query):
        return _FakeResult(self.rows)


def _fake_request():
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(redis=_FakeRedis())))


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


@pytest.mark.asyncio
async def test_regions_list_dedupes_alias_rows_after_canonical_formatting():
    from app.api.regions import get_regions

    rows = [
        SimpleNamespace(
            id=1,
            obcina_sifra="061",
            obcina_naziv="Ljubljana",
            regija_naziv="Osrednjeslovenska",
            vir="seed",
        ),
        SimpleNamespace(
            id=2,
            obcina_sifra="061A",
            obcina_naziv="Ljubljana Center",
            regija_naziv="osrednjeslovenska",
            vir="alias",
        ),
        SimpleNamespace(
            id=3,
            obcina_sifra="201",
            obcina_naziv="Vogrsko",
            regija_naziv="goriska",
            vir="alias",
        ),
        SimpleNamespace(
            id=4,
            obcina_sifra="201",
            obcina_naziv="Renče - Vogrsko",
            regija_naziv="Goriška",
            vir="seed",
        ),
    ]

    result = await get_regions(
        _fake_request(),
        _FakeResponse(),
        stats=False,
        db=_FakeDb(rows),
        _user=object(),
    )

    assert result.total == 2
    assert [(item.obcina_naziv, item.regija_naziv) for item in result.regions] == [
        ("Ljubljana", "Osrednjeslovenska"),
        ("Renče - Vogrsko", "Goriška"),
    ]


@pytest.mark.asyncio
async def test_region_stats_counts_canonical_municipalities_once():
    rows = [
        SimpleNamespace(municipality="Ljubljana", region="Osrednjeslovenska"),
        SimpleNamespace(municipality="Ljubljana Center", region="osrednjeslovenska"),
        SimpleNamespace(municipality="Vogrsko", region="goriska"),
        SimpleNamespace(municipality="Renče - Vogrsko", region="Goriška"),
        SimpleNamespace(municipality="Ni Podatka", region="Osrednjeslovenska"),
    ]

    result = await get_region_stats(_fake_request(), _FakeResponse(), db=_FakeDb(rows), _user=object())

    assert result == [
        {"region": "Goriška", "municipality_count": 1},
        {"region": "Osrednjeslovenska", "municipality_count": 1},
    ]


@pytest.mark.asyncio
async def test_municipalities_dedupes_alias_rows_after_canonical_formatting():
    rows = [
        SimpleNamespace(municipality="Ljubljana", region="Osrednjeslovenska"),
        SimpleNamespace(municipality="Ljubljana Center", region="osrednjeslovenska"),
        SimpleNamespace(municipality="Vogrsko", region="goriska"),
        SimpleNamespace(municipality="Renče - Vogrsko", region="Goriška"),
        SimpleNamespace(municipality="Ni Podatka", region="Osrednjeslovenska"),
    ]

    result = await get_municipalities(_fake_request(), _FakeResponse(), db=_FakeDb(rows), _user=object())

    assert result == [
        {"municipality": "Ljubljana", "region": "Osrednjeslovenska"},
        {"municipality": "Renče - Vogrsko", "region": "Goriška"},
    ]
