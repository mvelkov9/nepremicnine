"""Direct stats route unit tests that avoid the HTTP client harness."""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from app.api.stats import map_transactions, market_home, regions_stats, trend
from app.utils.municipality import municipality_slug


class _FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}

    async def get(self, key: str):
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self.store[key] = value


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

    result = await market_home(_fake_request(), property_type="Stanovanje", _user=object())

    assert result["active_property_type"] == "Stanovanje"
    assert result["headline"]["total_records"] == 3
    assert all(item["property_type"] == "stanovanje" for item in result["latest_sales"])


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

    result = await regions_stats(_fake_request(), property_type="hisa", _user=object())

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

    result = await trend(_fake_request(), property_type="stanovanje", _user=object())

    assert result
    assert sum(item["count"] for item in result) == 3
    assert all("stanovanje" in item["by_type"] for item in result if item["by_type"])


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
