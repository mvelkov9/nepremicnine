"""Direct stats route unit tests that avoid the HTTP client harness."""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from app.api.stats import (
    build_common_stats_cache_entries,
    comparables,
    map_transactions,
    market_home,
    municipality_detail,
    naselja,
    overview,
    price_distribution,
    regions_stats,
    trend,
)
from app.utils.municipality import municipality_slug


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


def _fake_request():
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(redis=_FakeRedis())))


def _build_market_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "price_eur": [210_000, 245_000, 590_000, 150_000, 330_000],
            "size_m2": [62, 71, 180, 58, 120],
            "uporabna_povrsina": [60, 69, 170, 55, 114],
            "municipality": ["Ljubljana", "Ljubljana", "Ljubljana", "Maribor", "Celje"],
            "property_type": ["stanovanje", "stanovanje", "hisa", "stanovanje", "hisa"],
            "source_label": ["2022", "2023", "2024", "2024", "2023"],
            "statistical_region": [
                "osrednjeslovenska",
                "osrednjeslovenska",
                "osrednjeslovenska",
                "podravska",
                "savinjska",
            ],
            "latitude": [100_000.0] * 5,
            "longitude": [460_000.0] * 5,
        }
    )


@pytest.mark.asyncio
async def test_market_home_property_type_filter_is_case_insensitive(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "app.api.stats._load_df",
        lambda property_type=None: (
            _build_market_df()
            if property_type is None
            else _build_market_df()[
                _build_market_df()["property_type"].astype(str).str.casefold() == str(property_type).casefold()
            ]
        ),
    )
    monkeypatch.setattr("app.api.stats._RAW_DF_CACHE", {"mtime": None, "df": None})
    monkeypatch.setattr("app.api.stats._PREPARED_DF_CACHE", {"mtime": None, "df": None})

    result = await market_home(_fake_request(), _FakeResponse(), property_type="Stanovanje", _user=object())

    assert result["active_property_type"] == "Stanovanje"
    assert result["headline"]["total_records"] == 3
    assert all(item["property_type"] == "stanovanje" for item in result["latest_sales"])


@pytest.mark.asyncio
async def test_market_home_uses_canonical_municipality_coverage(monkeypatch: pytest.MonkeyPatch):
    df = _build_market_df().copy()
    df.loc[len(df)] = {
        "price_eur": 99_000,
        "size_m2": 44,
        "uporabna_povrsina": 42,
        "municipality": "unknown",
        "property_type": "stanovanje",
        "source_label": "2026",
        "statistical_region": "osrednjeslovenska",
        "latitude": 100_000.0,
        "longitude": 460_000.0,
    }

    monkeypatch.setattr("app.api.stats._load_df", lambda property_type=None: df.copy())
    monkeypatch.setattr("app.api.stats._RAW_DF_CACHE", {"mtime": None, "df": None})
    monkeypatch.setattr("app.api.stats._PREPARED_DF_CACHE", {"mtime": None, "df": None})

    result = await market_home(_fake_request(), _FakeResponse(), _user=object())

    assert result["headline"]["latest_year"] == "2026"
    assert result["headline"]["municipalities_count"] == 3
    assert result["market_coverage"]["unresolved_rows"] == 1
    assert all(item["municipality"] != "unknown" for item in result["largest_markets"])


@pytest.mark.asyncio
async def test_market_home_recognizes_canonical_municipalities_with_spaces_and_hyphens(
    monkeypatch: pytest.MonkeyPatch,
):
    df = _build_market_df().copy()
    df.loc[len(df)] = {
        "price_eur": 275_000,
        "size_m2": 88,
        "uporabna_povrsina": 82,
        "municipality": "Hoče - Slivnica",
        "property_type": "stanovanje",
        "source_label": "2026",
        "statistical_region": "podravska",
        "latitude": 100_000.0,
        "longitude": 460_000.0,
    }

    monkeypatch.setattr("app.api.stats._load_df", lambda property_type=None: df.copy())
    monkeypatch.setattr("app.api.stats._RAW_DF_CACHE", {"mtime": None, "df": None})
    monkeypatch.setattr("app.api.stats._PREPARED_DF_CACHE", {"mtime": None, "df": None})

    result = await market_home(_fake_request(), _FakeResponse(), _user=object())

    assert result["headline"]["municipalities_count"] == 4
    assert result["market_coverage"]["present"] == 4
    assert result["market_coverage"]["noncanonical_rows"] == 0
    assert any(item["municipality"] == "Hoče - Slivnica" for item in result["largest_markets"])


@pytest.mark.asyncio
async def test_market_home_normalizes_known_municipality_aliases(monkeypatch: pytest.MonkeyPatch):
    df = _build_market_df().copy()
    df.loc[len(df)] = {
        "price_eur": 99_000,
        "size_m2": 44,
        "uporabna_povrsina": 42,
        "municipality": "Ljubljana Center",
        "property_type": "stanovanje",
        "source_label": "2026",
        "statistical_region": "osrednjeslovenska",
        "latitude": 100_000.0,
        "longitude": 460_000.0,
    }

    monkeypatch.setattr("app.api.stats._load_df", lambda property_type=None: df.copy())
    monkeypatch.setattr("app.api.stats._RAW_DF_CACHE", {"mtime": None, "df": None})
    monkeypatch.setattr("app.api.stats._PREPARED_DF_CACHE", {"mtime": None, "df": None})

    result = await market_home(_fake_request(), _FakeResponse(), _user=object())

    assert result["headline"]["municipalities_count"] == 3
    assert result["market_coverage"]["present"] == 3
    assert result["market_coverage"]["noncanonical_rows"] == 0
    assert all(item["municipality"] != "Ljubljana Center" for item in result["largest_markets"])


@pytest.mark.asyncio
async def test_market_home_treats_ambiguous_municipality_stubs_as_unresolved_unknowns(
    monkeypatch: pytest.MonkeyPatch,
):
    df = _build_market_df().copy()
    df.loc[len(df)] = {
        "price_eur": 99_000,
        "size_m2": 44,
        "uporabna_povrsina": 42,
        "municipality": "Sveti Jurij",
        "property_type": "stanovanje",
        "source_label": "2026",
        "statistical_region": "osrednjeslovenska",
        "latitude": 100_000.0,
        "longitude": 460_000.0,
    }

    monkeypatch.setattr("app.api.stats._load_df", lambda property_type=None: df.copy())
    monkeypatch.setattr("app.api.stats._RAW_DF_CACHE", {"mtime": None, "df": None})
    monkeypatch.setattr("app.api.stats._PREPARED_DF_CACHE", {"mtime": None, "df": None})

    result = await market_home(_fake_request(), _FakeResponse(), _user=object())

    assert result["headline"]["municipalities_count"] == 3
    assert result["market_coverage"]["present"] == 3
    assert result["market_coverage"]["unresolved_rows"] == 1
    assert result["market_coverage"]["noncanonical_rows"] == 0
    assert all(item["municipality"] != "Sveti Jurij" for item in result["largest_markets"])


@pytest.mark.asyncio
async def test_market_home_excludes_truly_noncanonical_municipalities_from_viewer_coverage(
    monkeypatch: pytest.MonkeyPatch,
):
    df = _build_market_df().copy()
    df.loc[len(df)] = {
        "price_eur": 99_000,
        "size_m2": 44,
        "uporabna_povrsina": 42,
        "municipality": "Nowhere Borough",
        "property_type": "stanovanje",
        "source_label": "2026",
        "statistical_region": "osrednjeslovenska",
        "latitude": 100_000.0,
        "longitude": 460_000.0,
    }

    monkeypatch.setattr("app.api.stats._load_df", lambda property_type=None: df.copy())
    monkeypatch.setattr("app.api.stats._RAW_DF_CACHE", {"mtime": None, "df": None})
    monkeypatch.setattr("app.api.stats._PREPARED_DF_CACHE", {"mtime": None, "df": None})

    result = await market_home(_fake_request(), _FakeResponse(), _user=object())

    assert result["headline"]["municipalities_count"] == 3
    assert result["market_coverage"]["present"] == 3
    assert result["market_coverage"]["noncanonical_rows"] == 1
    assert result["market_coverage"]["noncanonical_labels"][0]["label"] == "Nowhere Borough"
    assert all(item["municipality"] != "Nowhere Borough" for item in result["largest_markets"])


@pytest.mark.asyncio
async def test_comparables_keeps_location_context_when_property_type_has_no_local_rows(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        "app.api.stats._load_df",
        lambda property_type=None: (
            _build_market_df()
            if property_type is None
            else _build_market_df()[_build_market_df()["property_type"].astype(str).str.casefold() == str(property_type).casefold()]
        ),
    )
    monkeypatch.setattr("app.api.stats._RAW_DF_CACHE", {"mtime": None, "df": None})
    monkeypatch.setattr("app.api.stats._PREPARED_DF_CACHE", {"mtime": None, "df": None})

    result = await comparables(
        _fake_request(),
        municipality="Maribor",
        naselje=None,
        property_type="hisa",
        size_m2=120,
        year_built=1995,
        price_eur=300_000,
        limit=8,
        _user=object(),
    )

    assert result["summary"]["municipality_matched"] is True
    assert result["target"]["municipality"] == "Maribor"
    assert result["target"]["region"] == "Podravska"


@pytest.mark.asyncio
async def test_regions_stats_property_type_filter_scopes_region_counts(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "app.api.stats._load_df",
        lambda property_type=None: (
            _build_market_df()
            if property_type is None
            else _build_market_df()[_build_market_df()["property_type"] == property_type]
        ),
    )
    monkeypatch.setattr("app.api.stats._RAW_DF_CACHE", {"mtime": None, "df": None})
    monkeypatch.setattr("app.api.stats._PREPARED_DF_CACHE", {"mtime": None, "df": None})

    result = await regions_stats(_fake_request(), _FakeResponse(), property_type="hisa", _user=object())

    assert len(result) == 2
    assert sum(item["count"] for item in result) == 2


@pytest.mark.asyncio
async def test_trend_property_type_filter_returns_only_selected_type_rows(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "app.api.stats._load_df",
        lambda property_type=None: (
            _build_market_df()
            if property_type is None
            else _build_market_df()[_build_market_df()["property_type"] == property_type]
        ),
    )

    result = await trend(_fake_request(), _FakeResponse(), property_type="stanovanje", _user=object())

    assert result
    assert sum(item["count"] for item in result) == 3
    assert all("stanovanje" in item["by_type"] for item in result if item["by_type"])


@pytest.mark.asyncio
async def test_municipality_detail_filters_overview_by_property_type_and_year(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr("app.api.stats._load_df", lambda property_type=None: _build_market_df().copy())
    monkeypatch.setattr("app.api.stats._RAW_DF_CACHE", {"mtime": None, "df": None})
    monkeypatch.setattr("app.api.stats._PREPARED_DF_CACHE", {"mtime": None, "df": None})

    result = await municipality_detail(
        "ljubljana",
        _fake_request(),
        _FakeResponse(),
        property_type="stanovanje",
        year="2023",
        _user=object(),
    )

    assert result["municipality"] == "Ljubljana"
    assert result["overview"]["count"] == 1
    assert result["overview"]["median_price"] == 245000.0
    assert [item["year"] for item in result["year_trend"]] == ["2023"]
    assert result["property_type_mix"] == [{"property_type": "stanovanje", "count": 1, "share": 1.0}]
    assert all(item["property_type"] == "stanovanje" for item in result["recent_transactions"])


@pytest.mark.asyncio
async def test_map_transactions_exposes_price_band_legend_and_filter(monkeypatch: pytest.MonkeyPatch):
    df = _build_market_df().copy()
    df["_price_per_m2"] = df["price_eur"] / df["uporabna_povrsina"]
    df["_year"] = df["source_label"].astype(str)
    df["_municipality_slug"] = df["municipality"].map(municipality_slug)

    monkeypatch.setattr("app.api.stats._prepare_market_df", lambda: df.copy())

    result = await map_transactions(limit=1000, _user=object())
    filtered = await map_transactions(limit=1000, price_band="high", _user=object())

    assert result["meta"]["reason"] is None
    assert set(result["meta"]["legend"]["counts"]) == {"low", "mid", "high"}
    assert {item["price_band"] for item in result["transactions"]} == {"low", "mid", "high"}
    assert filtered["count"] >= 1
    assert all(item["price_band"] == "high" for item in filtered["transactions"])


@pytest.mark.asyncio
async def test_map_transactions_returns_all_filtered_points_when_limit_is_omitted(monkeypatch: pytest.MonkeyPatch):
    df = _build_market_df().copy()
    df["_price_per_m2"] = df["price_eur"] / df["uporabna_povrsina"]
    df["_year"] = df["source_label"].astype(str)
    df["_municipality_slug"] = df["municipality"].map(municipality_slug)
    df["_municipality_known"] = True

    monkeypatch.setattr("app.api.stats._prepare_market_df", lambda: df.copy())

    result = await map_transactions(_user=object())

    assert result["count"] == len(df)
    assert result["meta"]["truncated"] is False


@pytest.mark.asyncio
async def test_price_distribution_keeps_single_or_flat_price_dataset(monkeypatch: pytest.MonkeyPatch):
    df = pd.DataFrame(
        {
            "price_eur": [200_000.0, 200_000.0],
            "size_m2": [70.0, 70.0],
            "municipality": ["Ljubljana", "Ljubljana"],
            "property_type": ["stanovanje", "stanovanje"],
            "source_label": ["2024", "2024"],
        }
    )

    monkeypatch.setattr("app.api.stats._load_df", lambda property_type=None: df.copy())
    monkeypatch.setattr("app.api.stats._RAW_DF_CACHE", {"mtime": None, "df": None})
    monkeypatch.setattr("app.api.stats._PREPARED_DF_CACHE", {"mtime": None, "df": None})

    result = await price_distribution(_fake_request(), bins=5, _user=object())

    assert sum(result["counts"]) == 2
    assert len(result["bin_labels"]) == 5


@pytest.mark.asyncio
async def test_overview_uses_prepared_years_instead_of_raw_source_label_prefixes(monkeypatch: pytest.MonkeyPatch):
    df = pd.DataFrame(
        {
            "price_eur": [210_000.0, 220_000.0],
            "size_m2": [60.0, 65.0],
            "municipality": ["Ljubljana", "Ljubljana"],
            "property_type": ["stanovanje", "stanovanje"],
            "source_label": ["ETN Q1", "ETN Q4"],
            "transaction_date": ["2023-02-01", "2024-03-01"],
        }
    )

    monkeypatch.setattr("app.api.stats._load_df", lambda property_type=None: df.copy())
    monkeypatch.setattr("app.api.stats._RAW_DF_CACHE", {"mtime": None, "df": None})
    monkeypatch.setattr("app.api.stats._PREPARED_DF_CACHE", {"mtime": None, "df": None})

    result = await overview(_fake_request(), _FakeResponse(), _user=object())

    assert result["data_years"] == ["2023", "2024"]


@pytest.mark.asyncio
async def test_trend_uses_prepared_year_when_source_label_is_not_year_like(monkeypatch: pytest.MonkeyPatch):
    df = pd.DataFrame(
        {
            "price_eur": [210_000.0, 220_000.0],
            "size_m2": [60.0, 65.0],
            "municipality": ["Ljubljana", "Ljubljana"],
            "property_type": ["stanovanje", "stanovanje"],
            "source_label": ["ETN Q1", "ETN Q4"],
            "transaction_date": ["2023-02-01", "2024-03-01"],
        }
    )

    monkeypatch.setattr("app.api.stats._load_df", lambda property_type=None: df.copy())
    monkeypatch.setattr("app.api.stats._RAW_DF_CACHE", {"mtime": None, "df": None})
    monkeypatch.setattr("app.api.stats._PREPARED_DF_CACHE", {"mtime": None, "df": None})

    result = await trend(_fake_request(), _FakeResponse(), _user=object())

    assert [item["year"] for item in result] == ["2023", "2024"]
    assert sum(item["count"] for item in result) == 2


@pytest.mark.asyncio
async def test_overview_cache_key_rolls_when_training_signature_changes(monkeypatch: pytest.MonkeyPatch):
    request = _fake_request()

    df_one = pd.DataFrame(
        {
            "price_eur": [210_000.0],
            "size_m2": [60.0],
            "municipality": ["Ljubljana"],
            "property_type": ["stanovanje"],
            "source_label": ["2024"],
        }
    )
    df_two = pd.DataFrame(
        {
            "price_eur": [210_000.0, 220_000.0],
            "size_m2": [60.0, 65.0],
            "municipality": ["Ljubljana", "Maribor"],
            "property_type": ["stanovanje", "stanovanje"],
            "source_label": ["2024", "2024"],
        }
    )
    current_df = {"value": df_one}
    current_signature = {"value": ("train.csv", 1, 100)}

    monkeypatch.setattr("app.api.stats._load_df", lambda property_type=None: current_df["value"].copy())
    monkeypatch.setattr("app.api.stats._training_file_signature", lambda: current_signature["value"])
    monkeypatch.setattr("app.api.stats._RAW_DF_CACHE", {"mtime": None, "df": None})
    monkeypatch.setattr("app.api.stats._PREPARED_DF_CACHE", {"mtime": None, "df": None})

    first = await overview(request, _FakeResponse(), _user=object())

    current_df["value"] = df_two
    current_signature["value"] = ("train.csv", 2, 200)
    monkeypatch.setattr("app.api.stats._RAW_DF_CACHE", {"mtime": None, "df": None})
    monkeypatch.setattr("app.api.stats._PREPARED_DF_CACHE", {"mtime": None, "df": None})

    second = await overview(request, _FakeResponse(), _user=object())

    assert first["total_records"] == 1
    assert second["total_records"] == 2


def test_build_common_stats_cache_entries_warms_dashboard_and_explorer_defaults(
    monkeypatch: pytest.MonkeyPatch,
):
    prepared = _build_market_df().copy()
    prepared["_area"] = prepared["uporabna_povrsina"]
    prepared["_price_per_m2"] = (prepared["price_eur"] / prepared["_area"]).round(2)
    prepared["_year"] = prepared["source_label"]
    prepared["_sale_date"] = pd.to_datetime(prepared["source_label"] + "-01-01")
    prepared["_municipality_slug"] = prepared["municipality"].map(municipality_slug)
    prepared["_municipality_known"] = True
    monkeypatch.setattr("app.api.stats._prepare_market_df", lambda: prepared.copy())

    entries = build_common_stats_cache_entries()
    cache_keys = {key for key, _, _ttl in entries}

    assert any(":stats:overview:" in key for key in cache_keys)
    assert any(":stats:regions:" in key for key in cache_keys)
    assert any(":stats:price-distribution:" in key for key in cache_keys)
    assert any(":stats:market-home:" in key for key in cache_keys)
    assert any(":stats:trend:" in key for key in cache_keys)
    assert any(":stats:transactions:" in key and ":1:6:recent:desc" in key for key in cache_keys)
    assert any(":stats:municipalities:" in key and ":1:24:count:desc" in key for key in cache_keys)
    assert any(
        ":stats:regions-explorer:" in key and ":1:12:median_price_per_m2:desc" in key
        for key in cache_keys
    )


@pytest.mark.asyncio
async def test_summary_stats_routes_set_long_cache_control_headers(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.api.stats._load_df", lambda property_type=None: _build_market_df().copy())
    monkeypatch.setattr("app.api.stats._RAW_DF_CACHE", {"mtime": None, "df": None})
    monkeypatch.setattr("app.api.stats._PREPARED_DF_CACHE", {"mtime": None, "df": None})

    overview_response = _FakeResponse()
    regions_response = _FakeResponse()
    distribution_response = _FakeResponse()

    await overview(_fake_request(), overview_response, _user=object())
    await regions_stats(_fake_request(), regions_response, _user=object())
    await price_distribution(_fake_request(), distribution_response, bins=20, _user=object())

    assert overview_response.headers["Cache-Control"] == "private, max-age=86400"
    assert regions_response.headers["Cache-Control"] == "private, max-age=86400"
    assert distribution_response.headers["Cache-Control"] == "private, max-age=86400"


@pytest.mark.asyncio
async def test_naselja_returns_wgs84_coordinates_from_d96tm_inputs(monkeypatch: pytest.MonkeyPatch):
    df = pd.DataFrame(
        {
            "naselje": ["Center", "Center"],
            "_naselje_normalized": ["center", "center"],
            "municipality": ["Ljubljana", "Ljubljana"],
            "_municipality_slug": [municipality_slug("Ljubljana"), municipality_slug("Ljubljana")],
            "_municipality_known": [True, True],
            "statistical_region": ["Osrednjeslovenska", "Osrednjeslovenska"],
            "latitude": [100_000.0, 100_200.0],
            "longitude": [460_000.0, 460_200.0],
        }
    )

    monkeypatch.setattr("app.api.stats._prepare_market_df", lambda: df.copy())

    result = await naselja(_fake_request(), q="cent", municipality="Ljubljana", limit=10, _user=object())

    assert len(result) == 1
    assert result[0]["naselje"] == "Center"
    assert result[0]["municipality"] == "Ljubljana"
    assert result[0]["sample_count"] == 2
    assert 45.0 <= result[0]["latitude"] <= 47.5
    assert 13.0 <= result[0]["longitude"] <= 17.5


@pytest.mark.asyncio
async def test_comparables_does_not_prioritize_same_naselje_from_other_municipalities(
    monkeypatch: pytest.MonkeyPatch,
):
    df = pd.DataFrame(
        {
            "price_eur": [250_000, 249_000, 251_000, 355_000, 360_000, 365_000],
            "size_m2": [70, 70, 70, 100, 102, 104],
            "uporabna_povrsina": [70, 70, 70, 100, 102, 104],
            "municipality": ["Ljubljana", "Ljubljana", "Ljubljana", "Maribor", "Maribor", "Maribor"],
            "property_type": ["stanovanje"] * 6,
            "source_label": ["2024"] * 6,
            "statistical_region": [
                "osrednjeslovenska",
                "osrednjeslovenska",
                "osrednjeslovenska",
                "podravska",
                "podravska",
                "podravska",
            ],
            "latitude": [100_000.0] * 6,
            "longitude": [460_000.0] * 6,
            "naselje": ["Center", "Bežigrad", "Šiška", "Center", "Center", "Center"],
            "year_built": [2000, 2000, 2001, 1985, 1984, 1986],
        }
    )

    monkeypatch.setattr(
        "app.api.stats._load_df",
        lambda property_type=None: (
            df.copy()
            if property_type is None
            else df[df["property_type"].astype(str).str.casefold() == str(property_type).casefold()].copy()
        ),
    )
    monkeypatch.setattr("app.api.stats._RAW_DF_CACHE", {"mtime": None, "df": None})
    monkeypatch.setattr("app.api.stats._PREPARED_DF_CACHE", {"mtime": None, "df": None})

    result = await comparables(
        _fake_request(),
        municipality="Ljubljana",
        naselje="Center",
        property_type="stanovanje",
        size_m2=70,
        year_built=2000,
        price_eur=250_000,
        limit=3,
        _user=object(),
    )

    assert result["target"]["municipality"] == "Ljubljana"
    assert result["summary"]["count"] == 3
    assert [item["municipality"] for item in result["items"]] == ["Ljubljana", "Ljubljana", "Ljubljana"]
