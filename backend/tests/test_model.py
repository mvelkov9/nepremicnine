"""Smoke tests for model training (train_from_csv)."""

from __future__ import annotations

import os

import numpy as np
import pandas as pd


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
