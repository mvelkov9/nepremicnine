"""Fast unit tests for production-oriented model defaults."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def test_adaptive_hyperparams_keeps_rmse_loss_for_production_defaults(monkeypatch: pytest.MonkeyPatch):
    import app.services.model_service as ms

    monkeypatch.setattr(ms, "_get_catboost_task_type", lambda: "GPU")

    params = ms._adaptive_hyperparams(80_000, apply_gpu_adjustments=False)

    assert params["loss_function"] == "RMSE"


def test_build_recency_sample_weights_scales_from_one_to_four():
    import app.services.model_service as ms

    frame = pd.DataFrame({"transaction_year": [2020, 2021, 2022, 2023, 2024, 2025, 2026]})

    weights = ms._build_recency_sample_weights(frame)

    assert weights[0] == pytest.approx(1.0)
    assert weights[-1] == pytest.approx(4.0)
    assert np.all(np.diff(weights) > 0)


def test_build_model_preserves_explicit_large_type_gpu_overrides(monkeypatch: pytest.MonkeyPatch):
    import app.services.model_service as ms

    monkeypatch.setattr(ms, "_get_catboost_task_type", lambda: "GPU")

    model = ms._build_model(
        numeric_feats=["size_m2"],
        categorical_feats=["property_type"],
        n_samples=80_000,
        hp_overrides={
            "iterations": 8000,
            "learning_rate": 0.02,
            "depth": 8,
            "od_wait": 300,
            "max_ctr_complexity": 2,
        },
    )

    assert model.params["task_type"] == "GPU"
    assert model.params["iterations"] == 8000
    assert model.params["learning_rate"] == pytest.approx(0.02)
    assert model.params["depth"] == 8
    assert model.params["od_wait"] == 300
    assert model.params["max_ctr_complexity"] == 2
