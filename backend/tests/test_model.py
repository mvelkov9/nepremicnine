"""Smoke tests for model training (train_from_csv) and model API endpoints."""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from httpx import AsyncClient


def _make_synthetic_csv(path: str, n: int = 80) -> None:
    """Write a tiny synthetic CSV that satisfies train_from_csv requirements."""
    rng = np.random.default_rng(0)
    df = pd.DataFrame(
        {
            "price_eur": rng.uniform(80_000, 400_000, n),
            "size_m2": rng.uniform(30, 150, n),
            "rooms": rng.choice([1, 2, 3, 4], n),
            "floor": rng.integers(0, 10, n),
            "year_built": rng.integers(1960, 2020, n),
            "latitude": rng.uniform(45.8, 46.9, n),
            "longitude": rng.uniform(13.6, 16.5, n),
            "property_type": rng.choice(["Stanovanje", "Hiša"], n),
            "municipality": rng.choice(["Ljubljana", "Maribor", "Koper"], n),
            "statistical_region": rng.choice(["Osrednjeslovenska", "Podravska"], n),
        }
    )
    df.to_csv(path, index=False)


def test_train_from_csv_returns_expected_keys(tmp_path, monkeypatch):
    """train_from_csv must return a dict with the required top-level keys."""
    import app.services.model_service as ms

    monkeypatch.setattr(ms, "MODEL_DIR", str(tmp_path / "models"))
    csv_path = str(tmp_path / "synthetic.csv")
    _make_synthetic_csv(csv_path, n=80)

    result = ms.train_from_csv(csv_path)

    required_keys = {
        "model_path",
        "rows",
        "duration_sec",
        "global_metrics",
        "global_importance",
        "per_type_metrics",
        "per_region_metrics",
        "per_type_count",
        "segment_diagnostics",
    }
    assert required_keys.issubset(result.keys()), f"Missing keys: {required_keys - result.keys()}"


def test_train_from_csv_global_metrics(tmp_path, monkeypatch):
    """Global metrics dict must contain mae, rmse, r2, mape, median_ae."""
    import app.services.model_service as ms

    monkeypatch.setattr(ms, "MODEL_DIR", str(tmp_path / "models"))
    csv_path = str(tmp_path / "synthetic.csv")
    _make_synthetic_csv(csv_path, n=80)

    result = ms.train_from_csv(csv_path)
    metrics = result["global_metrics"]

    for key in ("mae", "rmse", "r2", "mape", "median_ae", "n_train", "n_test"):
        assert key in metrics, f"global_metrics missing '{key}'"
    assert metrics["n_train"] > 0
    assert metrics["n_test"] > 0


def test_train_from_csv_importance_populated(tmp_path, monkeypatch):
    """Feature importance dict must be non-empty after training."""
    import app.services.model_service as ms

    monkeypatch.setattr(ms, "MODEL_DIR", str(tmp_path / "models"))
    csv_path = str(tmp_path / "synthetic.csv")
    _make_synthetic_csv(csv_path, n=80)

    result = ms.train_from_csv(csv_path)
    assert len(result["global_importance"]) > 0, "global_importance should not be empty"


def test_train_from_csv_model_file_saved(tmp_path, monkeypatch):
    """train_from_csv must save a .joblib artifact to MODEL_DIR."""
    import app.services.model_service as ms

    model_dir = str(tmp_path / "models")
    monkeypatch.setattr(ms, "MODEL_DIR", model_dir)

    csv_path = str(tmp_path / "synthetic.csv")
    _make_synthetic_csv(csv_path, n=80)

    result = ms.train_from_csv(csv_path)
    assert os.path.exists(result["model_path"]), "Model .joblib file was not saved"


def test_train_from_csv_loads_training_data_preparation_metadata(tmp_path, monkeypatch):
    import app.services.model_service as ms

    monkeypatch.setattr(ms, "MODEL_DIR", str(tmp_path / "models"))
    csv_path = tmp_path / "synthetic.csv"
    _make_synthetic_csv(str(csv_path), n=80)
    metadata_path = csv_path.with_name(f"{csv_path.name}.metadata.json")
    metadata_path.write_text(
        json.dumps({"source": "etn_kpp_bulk", "filter_summary": {"building": [], "land": []}}),
        encoding="utf-8",
    )

    result = ms.train_from_csv(str(csv_path))

    assert result["data_preparation"]["source"] == "etn_kpp_bulk"


def test_train_from_csv_reports_ev_baseline_metrics(tmp_path, monkeypatch):
    import app.services.model_service as ms

    monkeypatch.setattr(ms, "MODEL_DIR", str(tmp_path / "models"))
    csv_path = tmp_path / "synthetic_ev.csv"

    rng = np.random.default_rng(9)
    n = 240
    size = rng.uniform(35, 160, n)
    price = size * rng.uniform(1800, 3200, n)
    benchmark = price * rng.uniform(0.82, 0.97, n)

    df = pd.DataFrame(
        {
            "price_eur": price,
            "size_m2": size,
            "rooms": rng.choice([1, 2, 3, 4], n),
            "floor": rng.integers(0, 8, n),
            "year_built": rng.integers(1960, 2020, n),
            "latitude": rng.uniform(45.8, 46.9, n),
            "longitude": rng.uniform(13.6, 16.5, n),
            "property_type": rng.choice(["stanovanje", "hisa"], n, p=[0.7, 0.3]),
            "municipality": rng.choice(["Ljubljana", "Maribor", "Koper"], n),
            "statistical_region": rng.choice(["Osrednjeslovenska", "Podravska"], n),
            "ev_benchmark_price_eur": benchmark,
            "ev_benchmark_source": rng.choice(["del_stavbe_enota", "parc_enota"], n, p=[0.85, 0.15]),
        }
    )
    df.to_csv(csv_path, index=False)

    result = ms.train_from_csv(str(csv_path))

    assert result["ev_baseline_metrics"] is not None
    assert result["ev_baseline_metrics"]["coverage_rows"] > 0
    assert "benchmark_metrics" in result["ev_baseline_metrics"]
    assert "model_metrics_on_coverage" in result["ev_baseline_metrics"]
    assert "delta_vs_model" in result["ev_baseline_metrics"]


def test_train_from_csv_reports_variant_benchmarks(tmp_path, monkeypatch):
    import app.services.model_service as ms

    monkeypatch.setattr(ms, "MODEL_DIR", str(tmp_path / "models"))
    csv_path = tmp_path / "synthetic_variant_benchmarks.csv"

    rng = np.random.default_rng(21)
    n = 260
    size = rng.uniform(40, 160, n)
    price = size * rng.uniform(1800, 3200, n)

    df = pd.DataFrame(
        {
            "price_eur": price,
            "size_m2": size,
            "rooms": rng.choice([1, 2, 3, 4], n),
            "floor": rng.integers(0, 8, n),
            "year_built": rng.integers(1960, 2021, n),
            "latitude": rng.uniform(45.8, 46.9, n),
            "longitude": rng.uniform(13.6, 16.5, n),
            "property_type": rng.choice(["stanovanje", "hisa"], n, p=[0.75, 0.25]),
            "municipality": rng.choice(["Ljubljana", "Maribor", "Koper"], n),
            "statistical_region": rng.choice(["Osrednjeslovenska", "Podravska"], n),
            "rn_address_match": rng.choice([0, 1], n, p=[0.35, 0.65]),
            "eid_statisticna_regija": rng.choice(["1111001", "1112002", "unknown"], n),
            "ev_st_etaz": rng.integers(1, 12, n),
            "ev_ima_vodovod": rng.choice([0, 1], n, p=[0.1, 0.9]),
            "ev_id_tip_stavbe": rng.choice(["10", "20", "30"], n),
            "kn_ko_polygon_match": rng.choice([0, 1], n, p=[0.15, 0.85]),
            "kn_ko_name": rng.choice(["Moste", "Center", "unknown"], n),
            "gji_vodovod_distance_m": rng.uniform(5, 500, n),
            "gji_vodovod_nearby_100m": rng.choice([0, 1], n, p=[0.45, 0.55]),
            "emv_zone_match": rng.choice([0, 1], n, p=[0.2, 0.8]),
            "emv_zone_level": rng.choice([1, 2, 3], n),
            "emv_zone_model": rng.choice(["STA", "HIS", "unknown"], n),
            "emv_zone_layer": rng.choice(["emv_sta", "emv_his"], n),
        }
    )
    df.to_csv(csv_path, index=False)

    result = ms.train_from_csv(str(csv_path))

    assert result["variant_benchmarks"] is not None
    assert result["variant_matrix"] is not None
    assert {"etn_only", "deterministic", "full_global", "production_combined"}.issubset(
        result["variant_benchmarks"].keys()
    )
    assert {"etn_only", "deterministic", "full_global"}.issubset(result["variant_matrix"].keys())
    assert result["variant_benchmarks"]["etn_only"]["metrics"]["n_train"] > 0
    assert result["variant_benchmarks"]["production_combined"]["metrics"]["n_test"] > 0
    assert result["variant_benchmarks"]["deterministic"]["enabled_sources"]["emv"] is False
    assert result["variant_benchmarks"]["deterministic"]["enabled_sources"]["kn"] is True
    assert result["variant_matrix"]["full_global"]["per_type_count"] >= 0


def test_train_from_csv_normalizes_mixed_type_categorical_enrichment_columns(tmp_path, monkeypatch):
    import app.services.model_service as ms

    monkeypatch.setattr(ms, "MODEL_DIR", str(tmp_path / "models"))
    csv_path = tmp_path / "synthetic_mixed_categories.csv"

    rng = np.random.default_rng(17)
    n = 260
    size = rng.uniform(40, 140, n)
    price = size * rng.uniform(1700, 3100, n)

    eid_region = rng.choice([1111001.0, 1112002.0, np.nan], n, p=[0.4, 0.4, 0.2])
    emv_model = rng.choice(["STA", "HIS", np.nan], n, p=[0.45, 0.35, 0.2])
    emv_layer = rng.choice(["emv_vredn_cone_STA", np.nan], n, p=[0.7, 0.3])

    df = pd.DataFrame(
        {
            "price_eur": price,
            "size_m2": size,
            "rooms": rng.choice([1, 2, 3, 4], n),
            "floor": rng.integers(0, 8, n),
            "year_built": rng.integers(1965, 2021, n),
            "latitude": rng.uniform(45.8, 46.9, n),
            "longitude": rng.uniform(13.6, 16.5, n),
            "property_type": rng.choice(["stanovanje", "hisa"], n, p=[0.75, 0.25]),
            "municipality": rng.choice(["Ljubljana", "Maribor", "Koper"], n),
            "statistical_region": rng.choice(["Osrednjeslovenska", "Podravska"], n),
            "lega_v_stavbi": rng.choice(["vmes", "pritlicje", np.nan], n, p=[0.45, 0.35, 0.2]),
            "eid_statisticna_regija": eid_region,
            "ev_id_konstrukcija": rng.choice([1.0, 2.0, np.nan], n, p=[0.45, 0.35, 0.2]),
            "ev_id_tip_stavbe": rng.choice([10.0, 20.0, np.nan], n, p=[0.4, 0.4, 0.2]),
            "ev_id_lega": rng.choice([33.0, 44.0, np.nan], n, p=[0.4, 0.4, 0.2]),
            "ev_id_dr_dst": rng.choice([29.0, 41.0, np.nan], n, p=[0.4, 0.4, 0.2]),
            "emv_zone_name": rng.choice(["Center", "Obrobje", np.nan], n, p=[0.35, 0.35, 0.3]),
            "emv_zone_model": emv_model,
            "emv_zone_layer": emv_layer,
        }
    )
    df.to_csv(csv_path, index=False)

    result = ms.train_from_csv(str(csv_path))

    assert result["combined_metrics"] is not None
    assert result["global_metrics"]["n_train"] > 0


def test_normalize_categorical_columns_returns_only_strings_for_missing_and_numeric_values():
    import app.services.model_service as ms

    df = pd.DataFrame(
        {
            "eid_statisticna_regija": [1111001.0, np.nan, "1112002"],
            "emv_zone_model": ["STA", None, "  "],
        }
    )

    normalized = ms._normalize_categorical_columns(
        df,
        ["eid_statisticna_regija", "emv_zone_model"],
    )

    assert normalized["eid_statisticna_regija"].tolist() == ["1111001.0", "unknown", "1112002"]
    assert normalized["emv_zone_model"].tolist() == ["STA", "unknown", "unknown"]
    assert {type(value).__name__ for value in normalized["eid_statisticna_regija"]} == {"str"}
    assert {type(value).__name__ for value in normalized["emv_zone_model"]} == {"str"}


def test_build_normalized_payload_accepts_new_training_features():
    import app.services.model_service as ms

    row = ms._build_normalized_payload(
        {
            "size_m2": 70,
            "municipality": "Ljubljana",
            "property_type": "stanovanje",
            "parcela_m2": 220,
            "prodani_delez_parcele": 0.75,
            "prodani_delez_dela_stavbe": 0.5,
            "gradbena_faza": 4,
            "stopnja_ddv": 22,
            "evidentiranost_dela_stavbe": 1,
            "atrij": 1,
            "ime_ko": "Moste",
            "naselje": "Ljubljana",
            "vrsta_dela_stavbe": "stanovanje",
            "vrsta_zemljisca": "stavbno",
            "vrsta_kupoprodajnega_posla": "1",
        },
        [
            "size_m2",
            "parcela_m2",
            "prodani_delez_parcele",
            "prodani_delez_dela_stavbe",
            "gradbena_faza",
            "stopnja_ddv",
            "evidentiranost_dela_stavbe",
            "atrij",
        ],
        [
            "municipality_normalized",
            "property_type",
            "ime_ko",
            "naselje",
            "vrsta_dela_stavbe",
            "vrsta_zemljisca",
            "vrsta_kupoprodajnega_posla",
        ],
        {
            "coords_by_municipality": {},
            "region_medians": {},
            "type_medians": {},
            "global_median_ppm2": 2000.0,
        },
    )

    assert row["parcela_m2"] == pytest.approx(220.0)
    assert row["prodani_delez_parcele"] == pytest.approx(0.75)
    assert row["prodani_delez_dela_stavbe"] == pytest.approx(0.5)
    assert row["gradbena_faza"] == pytest.approx(4.0)
    assert row["stopnja_ddv"] == pytest.approx(22.0)
    assert row["evidentiranost_dela_stavbe"] == pytest.approx(1.0)
    assert row["atrij"] == pytest.approx(1.0)
    assert row["ime_ko"] == "moste"
    assert row["naselje"] == "ljubljana"
    assert row["vrsta_dela_stavbe"] == "stanovanje"
    assert row["vrsta_zemljisca"] == "stavbno"
    assert row["vrsta_kupoprodajnega_posla"] == "1"


def test_select_type_specific_features_prefers_signal_over_noise():
    import app.services.model_service as ms

    rng = np.random.default_rng(42)
    n = 300
    signal = np.linspace(0, 1, n)
    target = 100000 + signal * 200000 + rng.normal(0, 5000, n)
    df = pd.DataFrame(
        {
            "size_m2": rng.uniform(40, 120, n),
            "signal_num": signal,
            "noise_num": rng.normal(0, 1, n),
            "signal_cat": np.where(signal > 0.5, "premium", "standard"),
            "noise_cat": rng.choice(["a", "b", "c"], n),
            "municipality_normalized": rng.choice(["ljubljana", "maribor"], n),
            "lega_v_stavbi": rng.choice(["pritlicje", "nadstropje"], n),
        }
    )

    num, cat, scores = ms._select_type_specific_features(
        df,
        target,
        ["size_m2", "signal_num", "noise_num"],
        ["municipality_normalized", "lega_v_stavbi", "signal_cat", "noise_cat"],
    )

    assert "signal_num" in num
    assert "signal_cat" in cat
    assert scores["signal_num"] > scores["noise_num"]
    assert scores["signal_cat"] > scores["noise_cat"]


def test_train_from_csv_uses_parcela_specific_feature_selection(tmp_path, monkeypatch):
    import app.services.model_service as ms

    monkeypatch.setattr(ms, "MODEL_DIR", str(tmp_path / "models"))

    rng = np.random.default_rng(7)
    n = 320
    size = rng.uniform(300, 2500, n)
    land_kind = rng.choice(["stavbno", "kmetijsko"], size=n, p=[0.55, 0.45])
    municipality = rng.choice(["ljubljana", "kranj", "koper"], n)
    price = size * np.where(land_kind == "stavbno", 140.0, 28.0) + rng.normal(0, 5000, n)

    df = pd.DataFrame(
        {
            "price_eur": np.clip(price, 5000, None),
            "size_m2": size,
            "parcela_m2": size,
            "prodani_delez_parcele": rng.choice([0.5, 1.0], n),
            "latitude": rng.uniform(45.8, 46.8, n),
            "longitude": rng.uniform(13.6, 16.3, n),
            "property_type": ["parcela"] * n,
            "municipality": municipality,
            "municipality_normalized": municipality,
            "statistical_region": rng.choice(["osrednjeslovenska", "gorenjska"], n),
            "vrsta_zemljisca": land_kind,
            "ime_ko": rng.choice(["Moste", "Kranj", "Koper"], n),
            "naselje": rng.choice(["Ljubljana", "Kranj", "Koper"], n),
            "transaction_year": rng.choice([2023, 2024, 2025], n),
        }
    )
    csv_path = tmp_path / "parcela.csv"
    df.to_csv(csv_path, index=False)

    result = ms.train_from_csv(str(csv_path))

    parcela_features = result["per_type_features"]["parcela"]
    assert parcela_features["selection_mode"] == "signal_scored_parcela"
    assert "vrsta_zemljisca" in parcela_features["categorical_features"]


def test_predict_combined_routed_batches_predictions_by_property_type():
    import app.services.model_service as ms

    class FakePipeline:
        def __init__(self, value):
            self.value = value
            self.calls = []

        def predict(self, frame):
            self.calls.append(len(frame))
            return np.full(len(frame), self.value, dtype=float)

    X_test = pd.DataFrame(
        {
            "property_type": ["stanovanje", "hisa", "stanovanje", "poslovni_prostor"],
            "size_m2": [60, 120, 75, 90],
        }
    )

    global_pipeline = FakePipeline(100.0)
    stanovanje_pipeline = FakePipeline(200.0)
    hisa_pipeline = FakePipeline(300.0)

    predicted = ms._predict_combined_routed(
        X_test,
        global_pipeline,
        {
            "stanovanje": {"pipeline": stanovanje_pipeline},
            "hisa": {"pipeline": hisa_pipeline},
        },
        target_transform="raw",
    )

    assert predicted.tolist() == [200.0, 300.0, 200.0, 100.0]
    assert global_pipeline.calls == [4]
    assert stanovanje_pipeline.calls == [2]
    assert hisa_pipeline.calls == [1]


def test_train_from_csv_emits_staged_progress_updates(tmp_path, monkeypatch):
    """Structured status callbacks should advance through multiple stages and progress values."""
    import app.services.model_service as ms

    monkeypatch.setattr(ms, "MODEL_DIR", str(tmp_path / "models"))
    csv_path = str(tmp_path / "synthetic.csv")
    _make_synthetic_csv(csv_path, n=120)

    events: list[tuple[str, int | None, int | None]] = []

    def status_callback(stage: str, **state):
        events.append((stage, state.get("progress"), state.get("current_model_progress")))

    ms.train_from_csv(csv_path, status_callback=status_callback)

    stages = [stage for stage, _, _ in events]
    progress_values = [value for _, value, _ in events if value is not None]

    assert "dataset_load" in stages
    assert "global_model" in stages
    assert "evaluation" in stages
    assert "artifact_save" in stages
    assert progress_values[0] >= 0
    assert progress_values[-1] >= 95
    assert len(set(progress_values)) > 5


# ══════════════════════════════════════════════════════════════════════════════
# API endpoint tests for /api/model/*
# ══════════════════════════════════════════════════════════════════════════════

_FAKE_MODEL_INFO = {
    "version": "test-v1",
    "trained_at": "2024-01-01T00:00:00",
    "rows": 100,
    "duration_sec": 5.0,
    "global_metrics": {"mae": 10_000, "rmse": 15_000, "r2": 0.85},
    "variant_matrix": {
        "etn_only": {
            "label": "ETN only",
            "variant_label": "etn_only",
            "enabled_sources": {"rn": False, "ev": False, "kn": False, "gji": False, "emv": False},
            "global_metrics": {"mae": 12_000, "rmse": 17_000, "r2": 0.8},
            "combined_metrics": {"mae": 12_200, "rmse": 17_200, "r2": 0.79},
            "per_type_metrics": {},
            "per_type_count": 0,
        }
    },
    "variant_benchmarks": {
        "etn_only": {
            "label": "ETN only",
            "variant_label": "etn_only",
            "enabled_sources": {"rn": False, "ev": False, "kn": False, "gji": False, "emv": False},
            "metrics": {"mae": 12_000, "rmse": 17_000, "r2": 0.8},
        }
    },
    "per_type_metrics": {},
    "per_region_metrics": {},
    "global_importance": {"size_m2": 0.5, "rooms": 0.3},
    "feature_labels": {"size_m2": "Velikost (m²)"},
    "per_type_count": 0,
    "type_models_trained": [],
    "coords_by_municipality": {},
    "segment_diagnostics": {"property_type": [{"segment": "parcela", "n": 100, "r2": 0.5, "mae": 1000}]},
}


# ── GET /api/model/info ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_model_info_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/model/info")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_model_info_no_model(client: AsyncClient, admin_headers: dict):
    """When no model file exists, the endpoint returns 404."""
    with patch("app.api.model.get_model_info", return_value=None):
        resp = await client.get("/api/model/info", headers=admin_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_model_info_with_model(client: AsyncClient, admin_headers: dict):
    with patch("app.api.model.get_model_info", return_value=_FAKE_MODEL_INFO):
        resp = await client.get("/api/model/info", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == "test-v1"
    assert data["rows"] == 100


# ── GET /api/model/importance ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_model_importance_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/model/importance")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_model_importance_no_model(client: AsyncClient, admin_headers: dict):
    with patch("app.api.model.get_model_info", return_value=None):
        resp = await client.get("/api/model/importance", headers=admin_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_model_importance_with_model(client: AsyncClient, admin_headers: dict):
    with patch("app.api.model.get_model_info", return_value=_FAKE_MODEL_INFO):
        resp = await client.get("/api/model/importance", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["feature"] == "size_m2"  # sorted by importance desc


# ── GET /api/model/diagnostics ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_model_diagnostics_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/model/diagnostics")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_model_diagnostics_no_model(client: AsyncClient, admin_headers: dict):
    with patch("app.api.model.get_model_info", return_value=None):
        resp = await client.get("/api/model/diagnostics", headers=admin_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_model_diagnostics_with_model(client: AsyncClient, admin_headers: dict):
    with patch("app.api.model.get_model_info", return_value=_FAKE_MODEL_INFO):
        resp = await client.get("/api/model/diagnostics", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "global_metrics" in data
    assert "per_type_metrics" in data
    assert "per_region_metrics" in data
    assert "ev_baseline_metrics" in data
    assert "variant_matrix" in data
    assert "variant_benchmarks" in data
    assert "segment_diagnostics" in data


# ── GET /api/model/runs ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_model_runs_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/model/runs")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_model_runs_empty(client: AsyncClient, admin_headers: dict):
    resp = await client.get("/api/model/runs", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


# ── DELETE /api/model/runs/clear ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_clear_model_runs_unauthenticated(client: AsyncClient):
    resp = await client.delete("/api/model/runs/clear")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_clear_model_runs_viewer_forbidden(client: AsyncClient, viewer_headers: dict):
    resp = await client.delete("/api/model/runs/clear", headers=viewer_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_clear_model_runs_admin_success(client: AsyncClient, admin_headers: dict):
    resp = await client.delete("/api/model/runs/clear", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["deleted"] == 0


# ── Enhanced diagnostics ─────────────────────────────────────────────────────

_ENHANCED_MODEL_INFO = {
    **_FAKE_MODEL_INFO,
    "train_rows": 80,
    "test_rows": 20,
    "used_features": ["size_m2", "rooms", "floor"],
    "model_type": "HistGradientBoostingRegressor",
    "data_preparation": {"source": "etn_kpp_bulk", "filter_summary": {"building": [], "land": []}},
    "ev_baseline_metrics": {
        "coverage_rows": 12,
        "coverage_ratio": 0.6,
        "benchmark_metrics": {"mae": 25000, "rmse": 31000, "r2": 0.5, "mape": 11.2, "median_ae": 21000},
        "model_metrics_on_coverage": {"mae": 18000, "rmse": 25000, "r2": 0.72, "mape": 8.3, "median_ae": 15000},
        "delta_vs_model": {"mae": 7000, "rmse": 6000, "r2": 0.22, "mape": 2.9, "median_ae": 6000},
    },
    "variant_benchmarks": {
        "etn_only": {
            "label": "ETN only",
            "variant_label": "etn_only",
            "enabled_sources": {"rn": False, "ev": False, "kn": False, "gji": False, "emv": False},
            "metrics": {"mae": 22000, "rmse": 30000, "r2": 0.61, "mape": 11.0, "median_ae": 18000},
            "delta_vs_full_global": {"mae": 4000, "rmse": 5000, "r2": -0.09, "mape": 1.3, "median_ae": 2500},
        }
    },
    "variant_matrix": {
        "etn_only": {
            "label": "ETN only",
            "variant_label": "etn_only",
            "enabled_sources": {"rn": False, "ev": False, "kn": False, "gji": False, "emv": False},
            "global_metrics": {"mae": 22000, "rmse": 30000, "r2": 0.61, "mape": 11.0, "median_ae": 18000},
            "combined_metrics": {"mae": 22300, "rmse": 30100, "r2": 0.6, "mape": 11.3, "median_ae": 18200},
            "per_type_metrics": {},
            "per_type_count": 0,
        }
    },
}


@pytest.mark.asyncio
async def test_diagnostics_includes_enhanced_fields(client: AsyncClient, admin_headers: dict):
    """When model exists, diagnostics should include train_rows, test_rows, used_features, model_type."""
    with patch("app.api.model.get_model_info", return_value=_ENHANCED_MODEL_INFO):
        resp = await client.get("/api/model/diagnostics", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["train_rows"] == 80
    assert data["test_rows"] == 20
    assert data["used_features"] == ["size_m2", "rooms", "floor"]
    assert data["model_type"] == "HistGradientBoostingRegressor"
    assert data["data_preparation"]["source"] == "etn_kpp_bulk"
    assert data["ev_baseline_metrics"]["coverage_rows"] == 12
    assert data["variant_matrix"]["etn_only"]["variant_label"] == "etn_only"
    assert data["variant_benchmarks"]["etn_only"]["variant_label"] == "etn_only"
    assert data["segment_diagnostics"]["property_type"][0]["segment"] == "parcela"
