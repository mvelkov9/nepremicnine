"""Smoke tests for model training (train_from_csv) and model API endpoints."""

from __future__ import annotations

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
    "per_type_metrics": {},
    "per_region_metrics": {},
    "global_importance": {"size_m2": 0.5, "rooms": 0.3},
    "feature_labels": {"size_m2": "Velikost (m²)"},
    "per_type_count": 0,
    "type_models_trained": [],
    "coords_by_municipality": {},
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
