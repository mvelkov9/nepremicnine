"""Smoke tests for model training (train_from_csv) and model API endpoints."""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from httpx import AsyncClient


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
    from types import SimpleNamespace

    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(redis=_FakeRedis())))


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
        "training_window",
        "segment_diagnostics",
    }
    assert required_keys.issubset(result.keys()), f"Missing keys: {required_keys - result.keys()}"
    assert isinstance(result["training_window"], dict)
    assert "rows_before" in result["training_window"]
    assert "rows_after" in result["training_window"]


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


def test_train_from_csv_supports_custom_artifact_path_without_overwriting_default(tmp_path, monkeypatch):
    import app.services.model_service as ms

    monkeypatch.setattr(ms, "MODEL_DIR", str(tmp_path / "models"))
    csv_path = str(tmp_path / "synthetic.csv")
    _make_synthetic_csv(csv_path, n=80)

    custom_model_path = tmp_path / "research" / "price_model_2020_2026.joblib"
    result = ms.train_from_csv(
        csv_path,
        model_output_path=str(custom_model_path),
        artifact_metadata={"variant_label": "recent_only_2020_2026"},
    )

    assert result["model_path"] == str(custom_model_path.resolve())
    assert custom_model_path.exists()
    assert not (tmp_path / "models" / "price_model.joblib").exists()


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


def test_select_best_training_candidate_prefers_lower_mape_then_higher_r2():
    import app.services.model_service as ms

    candidates = [
        {"metrics": {"mape": 30.0, "r2": 0.7, "mae": 10000}},
        {"metrics": {"mape": 28.0, "r2": 0.65, "mae": 12000}},
        {"metrics": {"mape": 28.0, "r2": 0.8, "mae": 11000}},
    ]

    best = ms._select_best_training_candidate(candidates)

    assert best == candidates[2]


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


def test_build_normalized_payload_prefers_recent_deployment_maps():
    import app.services.model_service as ms

    row = ms._build_normalized_payload(
        {
            "size_m2": 72,
            "municipality": "Ljubljana",
            "property_type": "Stanovanje",
            "statistical_region": "Osrednjeslovenska",
            "ime_ko": "Bezigrad",
            "naselje": "Ljubljana",
        },
        [
            "size_m2",
            "price_per_m2_region",
            "price_per_m2_type",
            "price_per_m2_municipality",
            "comp_type_muni_ppm2",
            "comp_type_ko_ppm2",
            "comp_type_naselje_ppm2",
            "price_per_m2_ko",
        ],
        ["municipality_normalized", "ime_ko", "naselje", "statistical_region"],
        {
            "coords_by_municipality": {},
            "coords_by_naselje": {},
            "region_medians": {"osrednjeslovenska": 1800.0},
            "type_medians": {"stanovanje": 1900.0},
            "municipality_medians": {"ljubljana": 2000.0},
            "global_median_ppm2": 1700.0,
            "type_muni_comp": {"stanovanje": {"ljubljana": np.log(2100.0)}},
            "type_ko_comp": {"stanovanje": {"bezigrad": np.log(2200.0)}},
            "type_naselje_comp": {"stanovanje": {"ljubljana": np.log(2300.0)}},
            "global_log_ppm2": np.log(1700.0),
            "eng_artifacts": {"ko_ppm2_map": {"bezigrad": 2050.0}, "global_median_ppm2_for_ko": 1700.0},
            "deploy_region_medians": {"osrednjeslovenska": 3200.0},
            "deploy_type_medians": {"stanovanje": 3300.0},
            "deploy_municipality_medians": {"ljubljana": 3400.0},
            "deploy_global_median_ppm2": 3000.0,
            "deploy_type_muni_comp": {"stanovanje": {"ljubljana": np.log(3500.0)}},
            "deploy_type_ko_comp": {"stanovanje": {"bezigrad": np.log(3600.0)}},
            "deploy_type_naselje_comp": {"stanovanje": {"ljubljana": np.log(3700.0)}},
            "deploy_global_log_ppm2": np.log(3000.0),
            "deploy_eng_artifacts": {"ko_ppm2_map": {"bezigrad": 3650.0}, "global_median_ppm2_for_ko": 3000.0},
        },
    )

    assert row["price_per_m2_region"] == pytest.approx(3200.0)
    assert row["price_per_m2_type"] == pytest.approx(3300.0)
    assert row["price_per_m2_municipality"] == pytest.approx(3400.0)
    assert row["comp_type_muni_ppm2"] == pytest.approx(np.log(3500.0))
    assert row["comp_type_ko_ppm2"] == pytest.approx(np.log(3600.0))
    assert row["comp_type_naselje_ppm2"] == pytest.approx(np.log(3700.0))
    assert row["price_per_m2_ko"] == pytest.approx(3650.0)


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


def test_sparse_residential_floor_strengthens_with_multiple_local_anchors():
    import app.services.model_service as ms

    floor = ms._sparse_residential_floor_eur(
        {
            "property_type": "stanovanje",
            "latitude": 100800,
            "longitude": 460900,
            "ime_ko": "Bezigrad",
            "naselje": "Ljubljana",
        },
        {
            "size_m2": 72,
            "comp_type_naselje_ppm2": np.log(3800.0),
            "comp_type_ko_ppm2": np.log(3850.0),
            "comp_type_muni_ppm2": np.log(3750.0),
            "knn_type_10_log_ppm2": np.log(2900.0),
            "price_per_m2_ko": 3025.0,
            "price_per_m2_municipality": 3050.0,
        },
        "stanovanje",
    )

    # floor_factor=1.0: has_fine_location from payload but normalized_row lacks ime_ko/naselje
    # => missing_micro_location=True => stanovanje gets max(0.88, 1.0)=1.0 boost
    assert floor == pytest.approx(1.0 * np.median([3800.0, 3850.0, 3750.0, 2900.0, 3025.0, 3050.0]) * 72)


def test_full_share_market_filter_drops_partial_sales():
    import app.services.model_service as ms

    df = pd.DataFrame(
        {
            "property_type": ["stanovanje", "stanovanje", "parcela", "parcela"],
            "prodani_delez_dela_stavbe": [1.0, 0.5, np.nan, np.nan],
            "prodani_delez_parcele": [np.nan, np.nan, 1.0, 0.25],
            "price_eur": [100000.0, 40000.0, 8000.0, 2000.0],
        }
    )

    filtered, info = ms._apply_full_share_market_filter(df)

    assert len(filtered) == 2
    assert info["rows_before"] == 4
    assert info["rows_after"] == 2
    assert info["rows_dropped"] == 2
    assert info["per_type"]["stanovanje"]["rows_after"] == 1
    assert info["per_type"]["parcela"]["rows_after"] == 1


def test_compute_per_type_blend_weight_searches_for_best_mape():
    import app.services.model_service as ms

    y_true = np.array([100.0, 200.0, 300.0, 400.0, 500.0] * 10)
    global_pred = np.array([120.0, 220.0, 320.0, 420.0, 520.0] * 10)
    per_type_pred = np.array([90.0, 190.0, 290.0, 390.0, 490.0] * 10)

    weight, metrics = ms._compute_per_type_blend_weight("stanovanje", y_true, global_pred, per_type_pred, len(y_true))

    assert 0.0 < weight < 1.0
    assert metrics["mape"] < ms._compute_metrics(y_true, global_pred)["mape"]
    assert metrics["mape"] < ms._compute_metrics(y_true, per_type_pred)["mape"]


def test_compute_engineered_features_handles_missing_optional_columns():
    import app.services.model_service as ms

    rng = np.random.default_rng(123)
    n_train = 40
    n_test = 12

    X_train = pd.DataFrame(
        {
            "size_m2": rng.uniform(35, 180, n_train),
            "longitude": rng.uniform(13.6, 16.5, n_train),
            "latitude": rng.uniform(45.8, 46.9, n_train),
        }
    )
    X_test = pd.DataFrame(
        {
            "size_m2": rng.uniform(35, 180, n_test),
            "longitude": rng.uniform(13.6, 16.5, n_test),
            "latitude": rng.uniform(45.8, 46.9, n_test),
        }
    )
    y_train = rng.uniform(60_000, 500_000, n_train)

    out_train, out_test, _ = ms._compute_engineered_features(X_train, y_train, X_test)

    assert "has_ev_data" in out_train.columns
    assert "has_ev_data" in out_test.columns
    assert out_train["has_ev_data"].sum() == 0
    assert out_test["has_ev_data"].sum() == 0
    assert "time_index" in out_train.columns
    assert "time_index" in out_test.columns


def test_catboost_model_fit_skips_user_callbacks_on_gpu(monkeypatch):
    import app.services.model_service as ms

    captured_fit_kwargs = {}

    class FakeCatBoostRegressor:
        def __init__(self, **params):
            self.params = params
            self.best_iteration_ = None
            self.tree_count_ = 9

        def fit(self, _train_pool, **kwargs):
            captured_fit_kwargs.update(kwargs)

    monkeypatch.setattr(ms, "CatBoostRegressor", FakeCatBoostRegressor)

    model = ms.CatBoostModel(
        numeric_features=["size_m2"],
        categorical_features=["property_type"],
        params={
            "iterations": 9,
            "depth": 3,
            "learning_rate": 0.1,
            "task_type": "GPU",
        },
    )

    X = pd.DataFrame({"size_m2": [55.0, 65.0, 75.0], "property_type": ["stanovanje", "stanovanje", "hisa"]})
    y = np.array([120000.0, 150000.0, 210000.0])

    model.fit(X, y, label="gpu-test", progress_callback=lambda *_args, **_kwargs: None)

    assert "callbacks" not in captured_fit_kwargs


def test_train_from_csv_uses_parcela_specific_feature_selection(tmp_path, monkeypatch):
    import app.services.model_service as ms

    monkeypatch.setattr(ms, "MODEL_DIR", str(tmp_path / "models"))

    rng = np.random.default_rng(7)
    n = 420
    size = rng.uniform(300, 2500, n)
    land_kind = rng.choice(["stavbno", "kmetijsko"], size=n, p=[0.55, 0.45])
    municipality = rng.choice(["ljubljana", "kranj", "koper"], n)
    price = size * np.where(land_kind == "stavbno", 140.0, 28.0) + rng.normal(0, 5000, n)

    df = pd.DataFrame(
        {
            "price_eur": np.clip(price, 5000, None),
            "size_m2": size,
            "parcela_m2": size,
            "prodani_delez_parcele": np.ones(n),
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

    global_pipeline = FakePipeline(1.0)
    stanovanje_pipeline = FakePipeline(2.0)
    hisa_pipeline = FakePipeline(3.0)

    predicted = ms._predict_combined_routed(
        X_test,
        global_pipeline,
        {
            "stanovanje": {"pipeline": stanovanje_pipeline},
            "hisa": {"pipeline": hisa_pipeline},
        },
        target_transform="raw",
    )

    assert predicted.tolist() == [2.0, 3.0, 2.0, 1.0]
    assert global_pipeline.calls == [4]
    assert stanovanje_pipeline.calls == [2]
    assert hisa_pipeline.calls == [1]


def test_predict_combined_routed_applies_blend_weight():
    import app.services.model_service as ms

    class FakePipeline:
        def __init__(self, value):
            self.value = value

        def predict(self, frame):
            return np.full(len(frame), self.value, dtype=float)

    X_test = pd.DataFrame(
        {
            "property_type": ["stanovanje", "hisa"],
            "size_m2": [100.0, 100.0],
        }
    )

    global_pipeline = FakePipeline(np.log(1000.0))
    stanovanje_pipeline = FakePipeline(np.log(2000.0))

    predicted = ms._predict_combined_routed(
        X_test,
        global_pipeline,
        {
            "stanovanje": {"pipeline": stanovanje_pipeline, "blend_weight": 0.25},
        },
        target_transform="log_ppm2",
    )

    # stanovanje: 25% per-type (200k) + 75% global (100k) = 125k
    assert predicted[0] == pytest.approx(125_000.0)
    # hisa: no type model => global only
    assert predicted[1] == pytest.approx(100_000.0)


def test_predict_combined_routed_honors_per_type_target_transform_override():
    import app.services.model_service as ms

    class FakePipeline:
        def __init__(self, value):
            self.value = value

        def predict(self, frame):
            return np.full(len(frame), self.value, dtype=float)

    X_test = pd.DataFrame(
        {
            "property_type": ["stanovanje", "hisa"],
            "size_m2": [100.0, 100.0],
        }
    )

    global_pipeline = FakePipeline(np.log(1000.0))
    stanovanje_pipeline = FakePipeline(np.log1p(220_000.0))

    predicted = ms._predict_combined_routed(
        X_test,
        global_pipeline,
        {
            "stanovanje": {
                "pipeline": stanovanje_pipeline,
                "blend_weight": 1.0,
                "target_transform": "log_price",
            },
        },
        target_transform="log_ppm2",
    )

    assert predicted[0] == pytest.approx(220_000.0)
    assert predicted[1] == pytest.approx(100_000.0)


def test_build_gurs_benchmark_payload_respects_global_target_transform_without_per_type_models(tmp_path, monkeypatch):
    import app.services.model_service as ms

    class FakePipeline:
        def __init__(self, value):
            self.value = value

        def predict(self, frame):
            return np.full(len(frame), self.value, dtype=float)

    csv_path = tmp_path / "benchmark.csv"
    csv_path.write_text("price_eur,size_m2\n1,1\n", encoding="utf-8")

    benchmark_frame = pd.DataFrame(
        {
            "size_m2": [100.0],
            "municipality": ["Ljubljana"],
            "municipality_normalized": ["ljubljana"],
            "statistical_region": ["osrednjeslovenska"],
            "property_type": ["stanovanje"],
            "transaction_year": [2024],
            "ev_benchmark_price_eur": [210_000.0],
            "ev_benchmark_source": ["del_stavbe_enota"],
            "source_label": ["2024"],
        }
    )
    y_values = np.array([200_000.0], dtype=float)

    monkeypatch.setattr(
        ms,
        "load_model",
        lambda: {
            "csv_path": str(csv_path),
            "per_type_models": {},
            "global_pipeline": FakePipeline(np.log1p(220_000.0)),
            "target_transform": "log_price",
        },
    )
    monkeypatch.setattr(
        ms,
        "_prepare_benchmark_frames_from_csv",
        lambda *_args, **_kwargs: (
            benchmark_frame.copy(),
            benchmark_frame.copy(),
            benchmark_frame.copy(),
            y_values.copy(),
            y_values.copy(),
        ),
    )

    payload = ms.build_gurs_benchmark_payload()

    assert payload["summary"]["status"] == "ready"
    assert payload["rows"][0]["model_price_eur"] == pytest.approx(220_000.0)
    assert payload["rows"][0]["gurs_price_eur"] == pytest.approx(210_000.0)


def test_build_gurs_benchmark_payload_returns_unavailable_for_incomplete_global_artifact(tmp_path, monkeypatch):
    import app.services.model_service as ms

    csv_path = tmp_path / "benchmark.csv"
    csv_path.write_text("price_eur,size_m2\n1,1\n", encoding="utf-8")

    benchmark_frame = pd.DataFrame(
        {
            "size_m2": [100.0],
            "municipality": ["Ljubljana"],
            "municipality_normalized": ["ljubljana"],
            "statistical_region": ["osrednjeslovenska"],
            "property_type": ["stanovanje"],
            "transaction_year": [2024],
            "ev_benchmark_price_eur": [210_000.0],
        }
    )
    y_values = np.array([200_000.0], dtype=float)

    monkeypatch.setattr(
        ms,
        "load_model",
        lambda: {
            "csv_path": str(csv_path),
            "per_type_models": {},
            "global_model": {},
            "global_pipeline": None,
        },
    )
    monkeypatch.setattr(
        ms,
        "_prepare_benchmark_frames_from_csv",
        lambda *_args, **_kwargs: (
            benchmark_frame.copy(),
            benchmark_frame.copy(),
            benchmark_frame.copy(),
            y_values.copy(),
            y_values.copy(),
        ),
    )

    payload = ms.build_gurs_benchmark_payload()

    assert payload["summary"]["status"] == "unavailable"
    assert payload["summary"]["detail"] == "The current model artifact is incomplete."
    assert payload["rows"] == []


def test_build_gurs_benchmark_payload_drops_nonfinite_predictions_and_nulls_single_row_r2(tmp_path, monkeypatch):
    import app.services.model_service as ms

    class FakePipeline:
        def predict(self, frame):
            return np.array([np.log1p(220_000.0), np.nan], dtype=float)

    csv_path = tmp_path / "benchmark.csv"
    csv_path.write_text("price_eur,size_m2\n1,1\n", encoding="utf-8")

    benchmark_frame = pd.DataFrame(
        {
            "size_m2": [100.0, 120.0],
            "municipality": ["Ljubljana", "Maribor"],
            "municipality_normalized": ["ljubljana", "maribor"],
            "statistical_region": ["osrednjeslovenska", "podravska"],
            "property_type": ["stanovanje", "stanovanje"],
            "transaction_year": [2024, 2024],
            "ev_benchmark_price_eur": [210_000.0, 190_000.0],
            "ev_benchmark_source": ["del_stavbe_enota", "del_stavbe_enota"],
            "source_label": ["2024", "2024"],
        }
    )
    y_values = np.array([200_000.0, 180_000.0], dtype=float)

    monkeypatch.setattr(
        ms,
        "load_model",
        lambda: {
            "csv_path": str(csv_path),
            "per_type_models": {},
            "global_pipeline": FakePipeline(),
            "target_transform": "log_price",
        },
    )
    monkeypatch.setattr(
        ms,
        "_prepare_benchmark_frames_from_csv",
        lambda *_args, **_kwargs: (
            benchmark_frame.copy(),
            benchmark_frame.copy(),
            benchmark_frame.copy(),
            y_values.copy(),
            y_values.copy(),
        ),
    )

    payload = ms.build_gurs_benchmark_payload()

    assert payload["summary"]["status"] == "ready"
    assert payload["summary"]["coverage_rows"] == 1
    assert len(payload["rows"]) == 1
    assert payload["rows"][0]["municipality"] == "Ljubljana"
    assert payload["summary"]["model_metrics"]["mae"] == pytest.approx(20_000.0)
    assert payload["summary"]["model_metrics"]["r2"] is None
    assert payload["summary"]["improvement_vs_gurs"]["r2"] is None


def test_sort_benchmark_rows_desc_keeps_missing_values_last():
    from app.api.model import _sort_benchmark_rows

    rows = [
        {"municipality": "Ljubljana", "improvement_pct": None},
        {"municipality": "Maribor", "improvement_pct": 18.0},
        {"municipality": "Celje", "improvement_pct": float("nan")},
        {"municipality": "Kranj", "improvement_pct": 5.0},
    ]

    result = _sort_benchmark_rows(rows, "improvement_pct", reverse=True)

    assert [item["municipality"] for item in result] == ["Maribor", "Kranj", "Ljubljana", "Celje"]


def test_compute_per_type_blend_weight_can_choose_global_per_type_or_blend():
    import app.services.model_service as ms

    y_true = np.array([100.0, 110.0, 120.0, 130.0] * 20)

    global_best_weight, _ = ms._compute_per_type_blend_weight(
        "stanovanje",
        y_true,
        global_pred=y_true.copy(),
        per_type_pred=np.full_like(y_true, 50.0),
        n_test=len(y_true),
    )
    per_type_best_weight, _ = ms._compute_per_type_blend_weight(
        "stanovanje",
        y_true,
        global_pred=np.full_like(y_true, 50.0),
        per_type_pred=y_true.copy(),
        n_test=len(y_true),
    )
    blend_best_weight, _ = ms._compute_per_type_blend_weight(
        "stanovanje",
        y_true,
        global_pred=np.full_like(y_true, 80.0),
        per_type_pred=np.full_like(y_true, 160.0),
        n_test=len(y_true),
    )

    assert global_best_weight <= 0.05
    assert per_type_best_weight >= 0.95
    assert 0.0 < blend_best_weight < 1.0


def test_fit_calibration_maps_builds_price_band_factors_for_large_type():
    import app.services.model_service as ms

    n = 180
    X_test = pd.DataFrame(
        {
            "property_type": ["hisa"] * n,
            "municipality_normalized": ["ljubljana"] * n,
            "naselje": ["ljubljana"] * n,
        }
    )
    y_pred = np.linspace(50_000.0, 300_000.0, n)
    y_true = np.where(y_pred < 130_000.0, y_pred * 0.65, y_pred * 1.8)

    calibration = ms._fit_calibration_maps(X_test, y_true, y_pred)

    assert "hisa" in calibration["price_band"]
    band_meta = calibration["price_band"]["hisa"]
    assert len(band_meta["factors"]) >= 2
    assert min(band_meta["factors"]) < 1.0
    assert max(band_meta["factors"]) > 1.0


def test_fit_calibration_maps_can_select_segment_feature_for_land_type():
    import app.services.model_service as ms

    n = 240
    land_use = (["41"] * (n // 2)) + (["3"] * (n // 2))
    X_test = pd.DataFrame(
        {
            "property_type": ["parcela"] * n,
            "municipality_normalized": ["koper"] * n,
            "naselje": ["koper"] * n,
            "parcela_namenska_raba": land_use,
            "vrsta_zemljisca": land_use,
        }
    )
    y_pred = np.full(n, 20_000.0)
    y_true = np.array([9_000.0] * (n // 2) + [42_000.0] * (n // 2))

    calibration = ms._fit_calibration_maps(X_test, y_true, y_pred)

    assert "parcela" in calibration["segment"]
    segment_meta = calibration["segment"]["parcela"]
    assert segment_meta["feature"] in {"parcela_namenska_raba", "vrsta_zemljisca"}
    assert min(segment_meta["factors"].values()) < 1.0
    assert max(segment_meta["factors"].values()) > 1.0


def test_lookup_calibration_factor_combines_location_and_price_band():
    import app.services.model_service as ms

    calibration = {
        "type": {"hisa": 1.2},
        "municipality": {"hisa": {"ljubljana": 1.1}},
        "naselje": {"hisa": {"bezigrad": 1.05}},
        "segment": {"hisa": {"feature": "kn_ggo_section", "factors": {"urban": 1.15}}},
        "price_band": {"hisa": {"edges": [200_000.0], "factors": [0.7, 1.8]}},
        "combined_clip": [0.35, 3.2],
    }

    factor_low, source_low = ms._lookup_calibration_factor(
        calibration,
        "hisa",
        "ljubljana",
        "bezigrad",
        120_000.0,
        row_context={"kn_ggo_section": "urban"},
    )
    factor_high, source_high = ms._lookup_calibration_factor(
        calibration,
        "hisa",
        "ljubljana",
        "bezigrad",
        260_000.0,
        row_context={"kn_ggo_section": "urban"},
    )

    assert factor_low == pytest.approx(1.05 * 1.15 * 0.7)
    assert source_low == "naselje+segment:kn_ggo_section+price_band_0"
    assert factor_high == pytest.approx(1.05 * 1.15 * 1.8)
    assert source_high == "naselje+segment:kn_ggo_section+price_band_1"


def test_apply_market_validity_filter_drops_low_value_tail_for_target_types():
    import app.services.model_service as ms

    df = pd.DataFrame(
        {
            "property_type": ["parcela", "parcela", "kmetijsko", "kmetijsko", "hisa", "garaza", "stanovanje"],
            "price_eur": [1000.0, 6000.0, 2000.0, 9000.0, 8000.0, 3000.0, 120000.0],
            "size_m2": [2000.0, 1000.0, 30.0, 20.0, 80.0, 10.0, 60.0],
            "municipality_normalized": ["koper", "koper", "unknown", "maribor", "celje", "celje", "ljubljana"],
        }
    )

    filtered, info = ms._apply_market_validity_filter(df, enabled=True)

    assert filtered["property_type"].tolist() == ["parcela", "kmetijsko", "stanovanje"]
    assert info["per_type"]["parcela"]["rows_dropped"] == 1
    assert info["per_type"]["kmetijsko"]["rows_dropped"] == 1
    assert info["per_type"]["hisa"]["rows_dropped"] == 1
    assert info["per_type"]["garaza"]["rows_dropped"] == 1


def test_apply_market_validity_filter_noops_when_disabled():
    import app.services.model_service as ms

    df = pd.DataFrame(
        {
            "property_type": ["parcela", "hisa"],
            "price_eur": [1000.0, 5000.0],
            "size_m2": [2000.0, 50.0],
        }
    )

    filtered, info = ms._apply_market_validity_filter(df, enabled=False)

    assert filtered.equals(df)
    assert info["rows_after"] == len(df)


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
async def test_model_info_viewer_forbidden(client: AsyncClient, viewer_headers: dict):
    resp = await client.get("/api/model/info", headers=viewer_headers)
    assert resp.status_code == 403


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
async def test_model_diagnostics_viewer_forbidden(client: AsyncClient, viewer_headers: dict):
    resp = await client.get("/api/model/diagnostics", headers=viewer_headers)
    assert resp.status_code == 403


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


# ── GET /api/model/benchmark/gurs-summary ────────────────────────────────────


@pytest.mark.asyncio
async def test_gurs_benchmark_summary_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/model/benchmark/gurs-summary")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_gurs_benchmark_summary_viewer_forbidden(client: AsyncClient, viewer_headers: dict):
    resp = await client.get("/api/model/benchmark/gurs-summary", headers=viewer_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_gurs_benchmark_summary_admin_success(client: AsyncClient, admin_headers: dict):
    payload = {
        "summary": {
            "coverage_rows": 12,
            "model_metrics": {"mae": 18_000.0},
            "gurs_metrics": {"mae": 25_000.0},
            "improvement_vs_gurs": {"mae": 7_000.0, "avg_gain_eur": 5_500.0},
            "winners": {"model": 8, "gurs": 3, "tie": 1},
            "top_regions": [],
            "top_property_types": [],
            "top_years": [],
            "methodology": "shared_gurs_coverage_holdout",
            "status": "ready",
            "detail": None,
        }
    }
    with (
        patch("app.api.model.get_model_info", return_value=_FAKE_MODEL_INFO),
        patch("app.api.model._load_cached_gurs_benchmark_payload", return_value=payload),
    ):
        resp = await client.get("/api/model/benchmark/gurs-summary", headers=admin_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["coverage_rows"] == 12
    assert data["winners"]["model"] == 8
    assert data["improvement_vs_gurs"]["mae"] == 7000.0


@pytest.mark.asyncio
async def test_model_info_cache_key_rolls_when_model_signature_changes(monkeypatch):
    from app.api.model import model_info

    request = _fake_request()
    response = _FakeResponse()
    signatures = iter(["sig-a", "sig-b"])
    infos = iter(
        [
            {**_FAKE_MODEL_INFO, "version": "v1"},
            {**_FAKE_MODEL_INFO, "version": "v2"},
        ]
    )

    monkeypatch.setattr("app.api.model._model_cache_namespace", lambda include_research_report=False: next(signatures))
    monkeypatch.setattr("app.api.model.get_model_info", lambda: next(infos))

    first = await model_info(request, response, _user=object())
    second = await model_info(request, response, _user=object())

    assert first.version == "v1"
    assert second.version == "v2"


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
