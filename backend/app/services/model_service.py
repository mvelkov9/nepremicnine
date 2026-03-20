"""Model training & prediction service — HistGradientBoosting per-type architecture."""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable
from math import isnan
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import TargetEncoder

from app.services.data_processing_service import (
    EXCLUDED_PROPERTY_TYPES,
    enrich_training_df,
    load_training_metadata,
    read_csv_flexible,
)
from app.utils.municipality import normalize_municipality_name

logger = logging.getLogger(__name__)

NUMERIC_FEATURES = [
    "size_m2",
    "year_built",
    "rooms",
    "floor",
    "latitude",
    "longitude",
    "building_age",
    "novogradnja",
    "num_prostori",
    "has_klet",
    "has_garaza",
    "has_terasa",
    "has_shramba",
    "has_parking",
    "uporabna_povrsina",
    "parcela_m2",
    "prodani_delez_parcele",
    "prodani_delez_dela_stavbe",
    "gradbena_faza",
    "stavba_je_dokoncana",
    "ddv_vkljucen",
    "log_size_m2",
    "transaction_year",
    "transaction_quarter",
    "price_per_m2_region",
    "price_per_m2_type",
    "price_per_m2_municipality",
]

CATEGORICAL_FEATURES = [
    "municipality_normalized",
    "property_type",
    "statistical_region",
    "lega_v_stavbi",
    "ime_ko",
    "naselje",
    "vrsta_zemljisca",
    "vrsta_kupoprodajnega_posla",
]

PERTYPE_NUMERIC = [f for f in NUMERIC_FEATURES if f != "price_per_m2_type"]
PERTYPE_CATEGORICAL = [f for f in CATEGORICAL_FEATURES if f != "property_type"]

MIN_SAMPLES_PER_TYPE = 200

# Core features to always keep even with low fill rates (global model defaults)
ALWAYS_INCLUDE_NUMERIC = {
    "size_m2",
    "year_built",
    "novogradnja",
    "has_klet",
    "has_garaza",
    "has_terasa",
    "has_shramba",
    "has_parking",
    "prodani_delez_parcele",
    "prodani_delez_dela_stavbe",
    "gradbena_faza",
    "stavba_je_dokoncana",
    "log_size_m2",
    "transaction_year",
    "price_per_m2_region",
}

ALWAYS_INCLUDE_CATEGORICAL = {
    "municipality_normalized",
    "statistical_region",
    "lega_v_stavbi",
}

FEATURE_LABELS_SL: dict[str, str] = {
    "size_m2": "Velikost (m²)",
    "rooms": "Število sob",
    "year_built": "Leto izgradnje",
    "floor": "Nadstropje",
    "latitude": "GPS širina",
    "longitude": "GPS dolžina",
    "municipality_normalized": "Občina",
    "property_type": "Vrsta nepremičnine",
    "statistical_region": "Statistična regija",
    "building_age": "Starost stavbe",
    "log_size_m2": "Log velikost",
    "novogradnja": "Novogradnja",
    "num_prostori": "Št. prostorov",
    "has_klet": "Klet",
    "has_garaza": "Garaža",
    "has_terasa": "Terasa",
    "has_shramba": "Shramba",
    "has_parking": "Parkirno mesto",
    "uporabna_povrsina": "Uporabna površina",
    "parcela_m2": "Površina parcele",
    "prodani_delez_parcele": "Prodani delež parcele",
    "prodani_delez_dela_stavbe": "Prodani delež dela stavbe",
    "gradbena_faza": "Gradbena faza",
    "stopnja_ddv": "Stopnja DDV",
    "evidentiranost_dela_stavbe": "Evidentiranost dela stavbe",
    "atrij": "Atrij",
    "stavba_je_dokoncana": "Stavba dokončana",
    "ddv_vkljucen": "DDV vključen",
    "lega_v_stavbi": "Lega v stavbi",
    "transaction_year": "Leto transakcije",
    "transaction_quarter": "Četrtletje transakcije",
    "price_per_m2_region": "€/m² regija",
    "price_per_m2_type": "€/m² tip",
    "price_per_m2_municipality": "€/m² občina",
    "ime_ko": "Katastrska občina",
    "naselje": "Naselje",
    "vrsta_dela_stavbe": "Vrsta dela stavbe",
    "vrsta_zemljisca": "Vrsta zemljišča",
    "vrsta_kupoprodajnega_posla": "Vrsta kupoprodajnega posla",
}

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "models")

_MIN_FILL_RATE = 0.10
_MIN_SIGNAL_SCORE = 0.01
_MAX_EXTRA_NUMERIC = 8
_MAX_EXTRA_CATEGORICAL = 8
_model_cache: dict | None = None
_model_cache_mtime: float = 0.0

PARCELA_ALWAYS_INCLUDE_NUMERIC = {
    "size_m2",
    "parcela_m2",
    "prodani_delez_parcele",
    "latitude",
    "longitude",
    "log_size_m2",
    "transaction_year",
    "price_per_m2_region",
    "price_per_m2_municipality",
    "ddv_vkljucen",
}

PARCELA_ALWAYS_INCLUDE_CATEGORICAL = {
    "municipality_normalized",
    "statistical_region",
    "ime_ko",
    "naselje",
    "vrsta_zemljisca",
}

# ── Type-specific feature configurations ─────────────────────────────
# Each type gets its own "always include" set — signal scoring adds more on top.

TYPE_FEATURE_CONFIGS: dict[str, dict[str, set[str]]] = {
    "stanovanje": {
        "always_numeric": {
            "size_m2",
            "year_built",
            "rooms",
            "floor",
            "building_age",
            "novogradnja",
            "log_size_m2",
            "transaction_year",
            "price_per_m2_region",
            "price_per_m2_municipality",
            "prodani_delez_dela_stavbe",
            "stavba_je_dokoncana",
            "uporabna_povrsina",
            "num_prostori",
        },
        "always_categorical": {
            "municipality_normalized",
            "statistical_region",
            "lega_v_stavbi",
            "ime_ko",
            "naselje",
        },
    },
    "hisa": {
        "always_numeric": {
            "size_m2",
            "year_built",
            "rooms",
            "building_age",
            "novogradnja",
            "log_size_m2",
            "transaction_year",
            "price_per_m2_region",
            "price_per_m2_municipality",
            "parcela_m2",
            "stavba_je_dokoncana",
            "uporabna_povrsina",
            "latitude",
            "longitude",
            "has_parking",
        },
        "always_categorical": {
            "municipality_normalized",
            "statistical_region",
            "ime_ko",
            "naselje",
        },
    },
    "parcela": {
        "always_numeric": PARCELA_ALWAYS_INCLUDE_NUMERIC,
        "always_categorical": PARCELA_ALWAYS_INCLUDE_CATEGORICAL,
    },
    "kmetijsko": {
        "always_numeric": {
            "size_m2",
            "parcela_m2",
            "prodani_delez_parcele",
            "latitude",
            "longitude",
            "log_size_m2",
            "transaction_year",
            "price_per_m2_region",
            "price_per_m2_municipality",
            "ddv_vkljucen",
        },
        "always_categorical": {
            "municipality_normalized",
            "statistical_region",
            "vrsta_zemljisca",
            "ime_ko",
        },
    },
    "garaza": {
        "always_numeric": {
            "size_m2",
            "year_built",
            "building_age",
            "novogradnja",
            "log_size_m2",
            "transaction_year",
            "price_per_m2_region",
            "price_per_m2_municipality",
            "stavba_je_dokoncana",
            "ddv_vkljucen",
            "prodani_delez_dela_stavbe",
        },
        "always_categorical": {
            "municipality_normalized",
            "statistical_region",
            "lega_v_stavbi",
            "ime_ko",
        },
    },
    "poslovni_prostor": {
        "always_numeric": {
            "size_m2",
            "year_built",
            "floor",
            "building_age",
            "novogradnja",
            "log_size_m2",
            "transaction_year",
            "price_per_m2_region",
            "price_per_m2_municipality",
            "uporabna_povrsina",
            "prodani_delez_dela_stavbe",
            "stavba_je_dokoncana",
            "ddv_vkljucen",
        },
        "always_categorical": {
            "municipality_normalized",
            "statistical_region",
            "lega_v_stavbi",
            "ime_ko",
            "naselje",
        },
    },
    "industrijski": {
        "always_numeric": {
            "size_m2",
            "year_built",
            "building_age",
            "novogradnja",
            "log_size_m2",
            "transaction_year",
            "price_per_m2_region",
            "price_per_m2_municipality",
            "uporabna_povrsina",
            "parcela_m2",
            "prodani_delez_dela_stavbe",
            "stavba_je_dokoncana",
        },
        "always_categorical": {
            "municipality_normalized",
            "statistical_region",
            "ime_ko",
        },
    },
    "turisticni": {
        "always_numeric": {
            "size_m2",
            "year_built",
            "rooms",
            "building_age",
            "novogradnja",
            "log_size_m2",
            "transaction_year",
            "price_per_m2_region",
            "price_per_m2_municipality",
            "uporabna_povrsina",
            "prodani_delez_dela_stavbe",
            "stavba_je_dokoncana",
        },
        "always_categorical": {
            "municipality_normalized",
            "statistical_region",
            "ime_ko",
            "naselje",
        },
    },
    "gostinstvo": {
        "always_numeric": {
            "size_m2",
            "year_built",
            "building_age",
            "log_size_m2",
            "transaction_year",
            "price_per_m2_region",
            "price_per_m2_municipality",
            "uporabna_povrsina",
            "stavba_je_dokoncana",
        },
        "always_categorical": {
            "municipality_normalized",
            "statistical_region",
        },
    },
}


def _filter_features(
    df: pd.DataFrame,
    candidate_numeric: list[str],
    candidate_categorical: list[str],
) -> tuple[list[str], list[str]]:
    """Filter features by fill rate, keeping ALWAYS_INCLUDE even when sparse."""
    numeric = [
        c
        for c in candidate_numeric
        if c in df.columns
        and (df[c].notna().mean() >= _MIN_FILL_RATE or (c in ALWAYS_INCLUDE_NUMERIC and df[c].notna().any()))
        and pd.to_numeric(df[c], errors="coerce").dropna().nunique() > 1
    ]
    categorical = [
        c
        for c in candidate_categorical
        if c in df.columns
        and (df[c].notna().mean() >= _MIN_FILL_RATE or (c in ALWAYS_INCLUDE_CATEGORICAL and df[c].notna().any()))
        and df[c].fillna("unknown").astype(str).nunique() > 1
    ]
    return numeric, categorical


def _adaptive_hyperparams(n_samples: int) -> dict:
    if n_samples > 20_000:
        return {
            "max_iter": 2000,
            "learning_rate": 0.02,
            "max_depth": 8,
            "min_samples_leaf": 30,
            "l2_regularization": 0.05,
        }
    if n_samples > 5000:
        return {
            "max_iter": 1500,
            "learning_rate": 0.03,
            "max_depth": 8,
            "min_samples_leaf": 25,
            "l2_regularization": 0.1,
        }
    if n_samples > 1000:
        return {
            "max_iter": 1000,
            "learning_rate": 0.04,
            "max_depth": 7,
            "min_samples_leaf": 20,
            "l2_regularization": 0.15,
        }
    if n_samples > 500:
        return {
            "max_iter": 800,
            "learning_rate": 0.05,
            "max_depth": 6,
            "min_samples_leaf": 15,
            "l2_regularization": 0.2,
        }
    return {
        "max_iter": 500,
        "learning_rate": 0.06,
        "max_depth": 5,
        "min_samples_leaf": 10,
        "l2_regularization": 0.3,
    }


def _adaptive_max_extras(n_samples: int) -> tuple[int, int]:
    """Return (max_extra_numeric, max_extra_categorical) based on dataset size."""
    if n_samples > 10_000:
        return 12, 10
    if n_samples > 3000:
        return 10, 8
    if n_samples > 1000:
        return 8, 6
    if n_samples > 500:
        return 6, 4
    return 4, 3


def _safe_abs(value: float | None) -> float:
    if value is None:
        return 0.0
    if isnan(value):
        return 0.0
    return abs(float(value))


def _score_numeric_feature(series: pd.Series, target: pd.Series) -> float:
    numeric = pd.to_numeric(series, errors="coerce")
    valid = numeric.notna() & target.notna()
    if valid.sum() < 50 or numeric[valid].nunique() <= 1:
        return 0.0
    return _safe_abs(numeric[valid].corr(target[valid], method="spearman"))


def _score_categorical_feature(series: pd.Series, target: pd.Series) -> float:
    categorical = series.fillna("unknown").astype(str)
    valid = target.notna()
    categorical = categorical[valid]
    target = target[valid]
    if len(categorical) < 50 or categorical.nunique() <= 1:
        return 0.0
    grouped = pd.DataFrame({"value": categorical, "target": target})
    means = grouped.groupby("value")["target"].mean()
    encoded = grouped["value"].map(means)
    return _safe_abs(encoded.corr(grouped["target"]))


def _select_type_specific_features(
    df: pd.DataFrame,
    target: np.ndarray,
    candidate_numeric: list[str],
    candidate_categorical: list[str],
    *,
    always_numeric: set[str] | None = None,
    always_categorical: set[str] | None = None,
    max_extra_numeric: int = _MAX_EXTRA_NUMERIC,
    max_extra_categorical: int = _MAX_EXTRA_CATEGORICAL,
) -> tuple[list[str], list[str], dict[str, float]]:
    filtered_numeric, filtered_categorical = _filter_features(df, candidate_numeric, candidate_categorical)
    target_series = pd.Series(np.log1p(np.maximum(target, 0)), index=df.index)
    always_numeric = ALWAYS_INCLUDE_NUMERIC if always_numeric is None else always_numeric
    always_categorical = ALWAYS_INCLUDE_CATEGORICAL if always_categorical is None else always_categorical

    scores: dict[str, float] = {}
    for col in filtered_numeric:
        scores[col] = _score_numeric_feature(df[col], target_series)
    for col in filtered_categorical:
        scores[col] = _score_categorical_feature(df[col], target_series)

    always_numeric_selected = [col for col in filtered_numeric if col in always_numeric]
    always_categorical_selected = [col for col in filtered_categorical if col in always_categorical]

    ranked_numeric = sorted(
        [col for col in filtered_numeric if col not in always_numeric_selected],
        key=lambda col: (scores.get(col, 0.0), df[col].notna().mean()),
        reverse=True,
    )
    ranked_categorical = sorted(
        [col for col in filtered_categorical if col not in always_categorical_selected],
        key=lambda col: (scores.get(col, 0.0), df[col].notna().mean()),
        reverse=True,
    )

    selected_numeric = (
        always_numeric_selected
        + [col for col in ranked_numeric if scores.get(col, 0.0) >= _MIN_SIGNAL_SCORE][:max_extra_numeric]
    )
    selected_categorical = (
        always_categorical_selected
        + [col for col in ranked_categorical if scores.get(col, 0.0) >= _MIN_SIGNAL_SCORE][:max_extra_categorical]
    )

    if "size_m2" in filtered_numeric and "size_m2" not in selected_numeric:
        selected_numeric = ["size_m2"] + selected_numeric

    return selected_numeric, selected_categorical, scores


def _build_pipeline(
    numeric_feats: list[str],
    categorical_feats: list[str],
    n_samples: int,
    y_train: np.ndarray | None = None,
    *,
    use_early_stopping: bool = False,
) -> Pipeline:
    numeric_transformer = SimpleImputer(strategy="median")
    categorical_transformer = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="constant", fill_value="unknown")),
            ("target_enc", TargetEncoder(smooth="auto")),
        ]
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, numeric_feats),
            ("cat", categorical_transformer, categorical_feats),
        ],
        remainder="drop",
    )

    hp = _adaptive_hyperparams(n_samples)

    # Early stopping requires warm_start=False (sklearn limitation).
    # Per-type models use early stopping; global model uses warm_start for progress.
    if use_early_stopping:
        model = HistGradientBoostingRegressor(
            loss="absolute_error",
            max_iter=hp["max_iter"],
            learning_rate=hp["learning_rate"],
            max_depth=hp["max_depth"],
            min_samples_leaf=hp.get("min_samples_leaf", 20),
            max_bins=255,
            l2_regularization=hp.get("l2_regularization", 0.1),
            early_stopping=True,
            validation_fraction=0.12,
            n_iter_no_change=30,
            random_state=42,
            warm_start=False,
            verbose=0,
        )
    else:
        model = HistGradientBoostingRegressor(
            loss="absolute_error",
            max_iter=hp["max_iter"],
            learning_rate=hp["learning_rate"],
            max_depth=hp["max_depth"],
            min_samples_leaf=hp.get("min_samples_leaf", 20),
            max_bins=255,
            l2_regularization=hp.get("l2_regularization", 0.1),
            random_state=42,
            warm_start=True,
            verbose=0,
        )

    return Pipeline([("preprocessor", preprocessor), ("regressor", model)])


def _compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    mask = y_true > 0
    y_t = y_true[mask]
    y_p = y_pred[mask]
    if len(y_t) == 0:
        return {}
    mae = float(mean_absolute_error(y_t, y_p))
    rmse = float(np.sqrt(mean_squared_error(y_t, y_p)))
    r2 = float(r2_score(y_t, y_p))
    mape = float(np.mean(np.abs((y_t - y_p) / y_t)) * 100)
    median_ae = float(np.median(np.abs(y_t - y_p)))
    return {"mae": mae, "rmse": rmse, "r2": r2, "mape": mape, "median_ae": median_ae}


def _build_segment_diagnostics(
    X_test: pd.DataFrame,
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> dict[str, list[dict[str, Any]]]:
    frame = X_test.copy()
    frame["y_true"] = y_true
    frame["y_pred"] = y_pred
    frame["abs_err"] = np.abs(frame["y_true"] - frame["y_pred"])
    frame["ape"] = np.where(frame["y_true"] > 0, frame["abs_err"] / frame["y_true"] * 100.0, np.nan)

    specs: list[tuple[str, str, int, pd.Series | None]] = [
        ("property_type", "property_type", 80, None),
        ("vrsta_kupoprodajnega_posla", "sale_type", 80, None),
        ("transaction_year", "transaction_year", 80, None),
        (
            "vrsta_zemljisca",
            "parcel_land_type",
            80,
            frame.get("property_type", pd.Series(index=frame.index, dtype="object")) == "parcela",
        ),
    ]

    diagnostics: dict[str, list[dict[str, Any]]] = {}
    for column, key, min_count, mask in specs:
        if column not in frame.columns:
            continue
        scoped = frame.loc[mask] if mask is not None else frame
        if scoped.empty:
            continue

        rows: list[dict[str, Any]] = []
        for segment, group in scoped.groupby(column, dropna=False):
            if len(group) < min_count:
                continue
            metrics = _compute_metrics(group["y_true"].to_numpy(), group["y_pred"].to_numpy())
            if not metrics:
                continue
            rows.append(
                {
                    "segment": "unknown" if pd.isna(segment) else str(segment),
                    "n": int(len(group)),
                    "r2": round(float(metrics.get("r2", 0.0)), 6),
                    "mae": round(float(metrics.get("mae", 0.0)), 2),
                    "rmse": round(float(metrics.get("rmse", 0.0)), 2),
                    "mape": round(float(metrics.get("mape", 0.0)), 2) if metrics.get("mape") is not None else None,
                    "median_ae": round(float(metrics.get("median_ae", 0.0)), 2),
                }
            )

        if rows:
            diagnostics[key] = sorted(rows, key=lambda item: (item["r2"], -item["n"], item["mae"]))

    return diagnostics


def _overall_training_progress(current_model_index: int, total_models: int, fitted: int, total: int) -> int:
    model_start = 18
    model_end = 88
    safe_total_models = max(total_models, 1)
    safe_total_trees = max(total, 1)
    completed_models = max(current_model_index - 1, 0)
    model_fraction = (completed_models + min(max(fitted, 0), safe_total_trees) / safe_total_trees) / safe_total_models
    return int(round(model_start + (model_end - model_start) * model_fraction))


def _normalize_model_label(label: str) -> str:
    if label == "global":
        return "global"
    if label.startswith("type:"):
        return label.split(":", 1)[1]
    return label


def _train_single_model(
    pipeline: Pipeline,
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    X_test: pd.DataFrame,
    y_test: np.ndarray,
    label: str,
    progress_callback: Callable | None = None,
    *,
    log_target: bool = False,
) -> dict:
    preprocessor = pipeline.named_steps["preprocessor"]
    regressor = pipeline.named_steps["regressor"]
    total_trees = regressor.max_iter

    # Log-transform target: trains on log(1+y), predicts in log-space then expm1
    y_fit = np.log1p(y_train) if log_target else y_train

    # Fit preprocessor ONCE and transform data (TargetEncoder uses y_fit)
    X_train_t = preprocessor.fit_transform(X_train, y_fit)
    X_test_t = preprocessor.transform(X_test)

    use_warm_start = regressor.warm_start

    if use_warm_start:
        # Warm-start loop for progress reporting (global model)
        chunk_size = max(50, total_trees // 20)
        fitted_trees = 0
        while fitted_trees < total_trees:
            next_target = min(fitted_trees + chunk_size, total_trees)
            regressor.max_iter = next_target
            regressor.fit(X_train_t, y_fit)
            fitted_trees = next_target
            if progress_callback:
                progress_callback(label, fitted_trees, total_trees)
    else:
        # Single fit with early stopping (per-type models)
        regressor.fit(X_train_t, y_fit)
        actual_trees = regressor.n_iter_
        if progress_callback:
            progress_callback(label, actual_trees, total_trees)

    y_pred_raw = regressor.predict(X_test_t)
    y_pred = np.maximum(np.expm1(y_pred_raw), 0) if log_target else y_pred_raw
    metrics = _compute_metrics(y_test, y_pred)
    metrics["n_train"] = len(X_train)
    metrics["n_test"] = len(X_test)

    importance = {}
    try:
        feat_names = preprocessor.get_feature_names_out()
        try:
            importance_sample_size = min(len(X_test_t), 5000)
            if len(X_test_t) > importance_sample_size:
                sample_idx = np.random.default_rng(42).choice(len(X_test_t), size=importance_sample_size, replace=False)
                X_importance = X_test_t[sample_idx]
                y_importance = y_test[sample_idx]
            else:
                X_importance = X_test_t
                y_importance = y_test

            # Fix: permutation importance must use the same target space as the regressor
            if log_target:
                y_importance = np.log1p(y_importance)

            perm = permutation_importance(
                regressor,
                X_importance,
                y_importance,
                n_repeats=2,
                random_state=42,
                n_jobs=1,
            )
            importances = perm.importances_mean
        except Exception:
            importances = regressor.feature_importances_
        importance = dict(zip([str(n) for n in feat_names], [float(v) for v in importances], strict=False))
    except Exception:
        pass

    return {"metrics": metrics, "importance": importance}


def _predict_combined_routed(
    X_test: pd.DataFrame,
    global_pipeline: Pipeline,
    per_type_models: dict[str, dict[str, Any]],
    *,
    log_target: bool = False,
) -> np.ndarray:
    y_pred_raw = global_pipeline.predict(X_test)
    y_pred = np.maximum(np.expm1(y_pred_raw), 0) if log_target else y_pred_raw

    if not per_type_models or "property_type" not in X_test.columns:
        return y_pred

    property_types = X_test["property_type"].astype(str)
    for ptype, model_meta in per_type_models.items():
        mask = property_types == ptype
        if not mask.any():
            continue
        pt_raw = model_meta["pipeline"].predict(X_test.loc[mask])
        pt_pred = np.maximum(np.expm1(pt_raw), 0) if log_target else pt_raw
        y_pred[mask.to_numpy()] = pt_pred

    return y_pred


def train_from_csv(
    csv_path: str,
    progress_callback: Callable | None = None,
    status_callback: Callable | None = None,
) -> dict[str, Any]:
    """Train per-type + global models from a training CSV. Returns model metadata."""
    start = time.time()

    def emit_status(stage: str, progress: int, **extra):
        if status_callback:
            status_callback(
                stage=stage,
                progress=progress,
                elapsed_sec=round(time.time() - start, 2),
                **extra,
            )

    emit_status("dataset_load", 2)
    df = read_csv_flexible(csv_path)
    emit_status("feature_prep", 8, rows=len(df))
    df = enrich_training_df(df)

    # Clean price
    df["price_eur"] = pd.to_numeric(df.get("price_eur"), errors="coerce")
    df = df.dropna(subset=["price_eur"])
    df = df[df["price_eur"] > 0]

    # Exclude non-predictable types
    if "property_type" in df.columns:
        df = df[~df["property_type"].isin(EXCLUDED_PROPERTY_TYPES)]

    # Ensure size_m2 is numeric before split
    df["size_m2"] = pd.to_numeric(df.get("size_m2"), errors="coerce")

    y = df["price_eur"].values
    X = df.drop(columns=["price_eur"], errors="ignore")

    emit_status("feature_prep", 14, rows=len(df))

    # Stratified split preserves type distribution in train and test sets
    stratify_col = X["property_type"] if "property_type" in X.columns else None
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=stratify_col,
    )
    emit_status("training_setup", 18, rows=len(df))

    # Compute group medians from TRAINING SET ONLY (prevent data leakage)
    train_with_price = X_train.copy()
    train_with_price["price_eur"] = y_train
    valid = train_with_price[train_with_price["size_m2"] > 0].copy()
    valid["ppm2"] = valid["price_eur"] / valid["size_m2"]

    region_medians = (
        valid.groupby("statistical_region")["ppm2"].median().to_dict() if "statistical_region" in valid.columns else {}
    )
    type_medians = valid.groupby("property_type")["ppm2"].median().to_dict() if "property_type" in valid.columns else {}
    global_median_ppm2 = float(valid["ppm2"].median()) if len(valid) > 0 else 2000.0

    # Municipality-level price medians (finer granularity than region)
    municipality_medians: dict[str, float] = {}
    if "municipality_normalized" in valid.columns:
        muni_groups = valid.groupby("municipality_normalized")["ppm2"]
        for muni, group in muni_groups:
            if len(group) >= 10:
                municipality_medians[str(muni)] = float(group.median())
            else:
                # Fall back to region median for small municipalities
                region = valid.loc[group.index, "statistical_region"].mode()
                region_key = region.iloc[0] if len(region) > 0 else "neznana"
                municipality_medians[str(muni)] = region_medians.get(region_key, global_median_ppm2)

    # Apply to train and test sets separately
    X_train["price_per_m2_region"] = (
        X_train.get("statistical_region", pd.Series()).map(region_medians).fillna(global_median_ppm2)
    )
    X_train["price_per_m2_type"] = (
        X_train.get("property_type", pd.Series()).map(type_medians).fillna(global_median_ppm2)
    )
    X_train["price_per_m2_municipality"] = (
        X_train.get("municipality_normalized", pd.Series()).map(municipality_medians).fillna(global_median_ppm2)
    )
    X_test["price_per_m2_region"] = (
        X_test.get("statistical_region", pd.Series()).map(region_medians).fillna(global_median_ppm2)
    )
    X_test["price_per_m2_type"] = X_test.get("property_type", pd.Series()).map(type_medians).fillna(global_median_ppm2)
    X_test["price_per_m2_municipality"] = (
        X_test.get("municipality_normalized", pd.Series()).map(municipality_medians).fillna(global_median_ppm2)
    )

    global_num, global_cat = _filter_features(X_train, NUMERIC_FEATURES, CATEGORICAL_FEATURES)
    data_preparation = load_training_metadata(csv_path)

    # Global model
    model_start_times: dict[str, float] = {}
    global_pipeline = _build_pipeline(global_num, global_cat, len(X_train))
    per_type_models: dict[str, Pipeline] = {}
    per_type_metrics: dict[str, dict] = {}
    per_type_feature_usage: dict[str, dict[str, Any]] = {}

    eligible: list[str] = []
    if "property_type" in X_train.columns:
        type_counts = X_train["property_type"].value_counts()
        eligible = type_counts[type_counts >= MIN_SAMPLES_PER_TYPE].index.tolist()

    total_models = 1 + len(eligible)

    def training_progress(label: str, fitted_trees: int, total_trees: int):
        if progress_callback:
            progress_callback(label, fitted_trees, total_trees)

        current_model = _normalize_model_label(label)
        current_index = 1 if label == "global" else eligible.index(current_model) + 2
        now = time.time()
        model_started = model_start_times.setdefault(label, now)
        model_elapsed = max(now - model_started, 0.001)
        trees_per_sec = fitted_trees / model_elapsed if fitted_trees > 0 else None
        eta_sec = ((total_trees - fitted_trees) / trees_per_sec) if trees_per_sec else None
        emit_status(
            "global_model" if label == "global" else "per_type_models",
            _overall_training_progress(current_index, total_models, fitted_trees, total_trees),
            rows=len(df),
            current_model=current_model,
            current_model_index=current_index,
            total_models=total_models,
            current_model_progress=int(round((fitted_trees / max(total_trees, 1)) * 100)),
            fitted_trees=fitted_trees,
            total_trees=total_trees,
            eta_sec=round(float(eta_sec), 2) if eta_sec is not None else None,
            trees_per_sec=round(float(trees_per_sec), 2) if trees_per_sec is not None else None,
        )

    emit_status(
        "global_model",
        18,
        rows=len(df),
        current_model="global",
        current_model_index=1,
        total_models=total_models,
        current_model_progress=0,
        fitted_trees=0,
        total_trees=global_pipeline.named_steps["regressor"].max_iter,
    )
    global_result = _train_single_model(
        global_pipeline,
        X_train,
        y_train,
        X_test,
        y_test,
        "global",
        training_progress,
        log_target=True,
    )

    # Per-type models — signal-scored features + early stopping + aggressive outlier removal
    if eligible:
        for ptype in eligible:
            mask_train = X_train["property_type"] == ptype
            mask_test = X_test["property_type"] == ptype
            Xt = X_train[mask_train].copy()
            yt = y_train[mask_train].copy()
            Xte = X_test[mask_test].copy()
            yte = y_test[mask_test]

            if len(Xte) < 10:
                continue

            # ── Aggressive per-type outlier removal ──────────────────────
            n_before = len(yt)

            # 1) IQR-based price outlier removal (tighter than percentile)
            q1, q3 = np.percentile(yt, [25, 75])
            iqr = q3 - q1
            price_lower = max(q1 - 2.0 * iqr, 0)
            price_upper = q3 + 2.5 * iqr
            price_mask = (yt >= price_lower) & (yt <= price_upper)

            # 2) Price-per-m² outlier removal within each type
            size_col_vals = pd.to_numeric(Xt.get("size_m2"), errors="coerce")
            ppm2_mask = np.ones(len(yt), dtype=bool)
            valid_size = size_col_vals.notna() & (size_col_vals > 0)
            if valid_size.sum() > 50:
                ppm2 = np.where(valid_size, yt / size_col_vals.clip(lower=1), np.nan)
                ppm2_valid = ppm2[~np.isnan(ppm2)]
                if len(ppm2_valid) > 50:
                    ppm2_q1, ppm2_q3 = np.percentile(ppm2_valid, [5, 95])
                    ppm2_mask = np.isnan(ppm2) | ((ppm2 >= ppm2_q1) & (ppm2 <= ppm2_q3))

            combined_mask = price_mask & ppm2_mask
            if combined_mask.sum() >= MIN_SAMPLES_PER_TYPE:
                Xt = Xt[combined_mask]
                yt = yt[combined_mask]
                logger.info("Type %s: outlier removal %d → %d rows", ptype, n_before, len(yt))

            # Look up type-specific feature config, fall back to global defaults
            type_config = TYPE_FEATURE_CONFIGS.get(ptype, {})
            always_num = type_config.get("always_numeric", ALWAYS_INCLUDE_NUMERIC)
            always_cat = type_config.get("always_categorical", ALWAYS_INCLUDE_CATEGORICAL)

            # Adaptive max extras based on dataset size
            max_extra_num, max_extra_cat = _adaptive_max_extras(len(Xt))

            # Signal-scored feature selection for ALL types
            pt_num, pt_cat, pt_scores = _select_type_specific_features(
                Xt,
                yt,
                PERTYPE_NUMERIC,
                PERTYPE_CATEGORICAL,
                always_numeric=always_num,
                always_categorical=always_cat,
                max_extra_numeric=max_extra_num,
                max_extra_categorical=max_extra_cat,
            )
            selection_mode = f"signal_scored_{ptype}"

            # Per-type models: use early_stopping (no warm_start) for proper regularization
            pt_pipeline = _build_pipeline(pt_num, pt_cat, len(Xt), use_early_stopping=True)
            emit_status(
                "per_type_models",
                _overall_training_progress(
                    eligible.index(ptype) + 2, total_models, 0, pt_pipeline.named_steps["regressor"].max_iter
                ),
                rows=len(df),
                current_model=str(ptype),
                current_model_index=eligible.index(ptype) + 2,
                total_models=total_models,
                current_model_progress=0,
                fitted_trees=0,
                total_trees=pt_pipeline.named_steps["regressor"].max_iter,
            )
            pt_result = _train_single_model(
                pt_pipeline,
                Xt,
                yt,
                Xte,
                yte,
                f"type:{ptype}",
                training_progress,
                log_target=True,
            )
            per_type_models[ptype] = {
                "pipeline": pt_pipeline,
                "numeric_features": pt_num,
                "categorical_features": pt_cat,
            }
            per_type_metrics[ptype] = pt_result["metrics"]
            per_type_feature_usage[ptype] = {
                "numeric_features": pt_num,
                "categorical_features": pt_cat,
                "selection_mode": selection_mode,
            }
            if pt_scores:
                per_type_feature_usage[ptype]["feature_scores"] = {
                    key: round(float(value), 6)
                    for key, value in sorted(pt_scores.items(), key=lambda item: item[1], reverse=True)
                }
    else:
        emit_status("per_type_models", 88, rows=len(df), total_models=total_models)

    # Per-region metrics (not separate models)
    emit_status("evaluation", 92, rows=len(df), total_models=total_models)
    per_region_metrics: dict[str, dict] = {}
    if "statistical_region" in X_test.columns:
        y_pred_all_raw = global_pipeline.predict(X_test)
        y_pred_all = np.maximum(np.expm1(y_pred_all_raw), 0)
        for region in X_test["statistical_region"].unique():
            mask = X_test["statistical_region"] == region
            if mask.sum() >= 10:
                per_region_metrics[str(region)] = _compute_metrics(y_test[mask], y_pred_all[mask])

    # Combined routing metrics: use per-type model when available, else global
    if per_type_models:
        y_pred_combined = _predict_combined_routed(X_test, global_pipeline, per_type_models, log_target=True)
        combined_metrics = _compute_metrics(y_test, y_pred_combined)
    else:
        y_pred_combined_raw = global_pipeline.predict(X_test)
        y_pred_combined = np.maximum(np.expm1(y_pred_combined_raw), 0)
        combined_metrics = global_result["metrics"]

    segment_diagnostics = _build_segment_diagnostics(X_test, y_test, y_pred_combined)

    # Municipality coordinates
    emit_status("artifact_save", 96, rows=len(df), total_models=total_models)
    coords_by_municipality: dict[str, dict] = {}
    coord_key = "municipality_normalized" if "municipality_normalized" in df.columns else "municipality"
    for col_pair in [(coord_key, "latitude", "longitude")]:
        if all(c in df.columns for c in col_pair):
            for mun, grp in df.groupby(col_pair[0]):
                lat = grp[col_pair[1]].median()
                lon = grp[col_pair[2]].median()
                if pd.notna(lat) and pd.notna(lon):
                    coords_by_municipality[str(mun)] = {
                        "lat": float(lat),
                        "lon": float(lon),
                    }

    duration = time.time() - start

    # Save artifact
    os.makedirs(MODEL_DIR, exist_ok=True)
    emit_status("finalizing", 99, rows=len(df), total_models=total_models)
    artifact = {
        "version": "5.0",
        "log_target": True,
        "global_model": {
            "pipeline": global_pipeline,
            "numeric_features": global_num,
            "categorical_features": global_cat,
        },
        # Backward compat
        "global_pipeline": global_pipeline,
        "per_type_models": per_type_models,
        "region_medians": region_medians,
        "type_medians": type_medians,
        "municipality_medians": municipality_medians,
        "global_median_ppm2": global_median_ppm2,
        "global_metrics": global_result["metrics"],
        "global_importance": global_result["importance"],
        "per_type_metrics": per_type_metrics,
        "per_region_metrics": per_region_metrics,
        "combined_metrics": combined_metrics,
        "coords_by_municipality": coords_by_municipality,
        "feature_labels": FEATURE_LABELS_SL,
        "trained_at": pd.Timestamp.now().isoformat(),
        "csv_path": csv_path,
        "rows": len(df),
        "train_rows": len(X_train),
        "test_rows": len(X_test),
        "used_features": global_num + global_cat,
        "per_type_features": per_type_feature_usage,
        "data_preparation": data_preparation,
        "segment_diagnostics": segment_diagnostics,
        "model_type": "HistGradientBoostingRegressor",
        "duration_sec": duration,
    }
    model_path = os.path.join(MODEL_DIR, "price_model.joblib")
    joblib.dump(artifact, model_path, compress=3)

    return {
        "model_path": model_path,
        "csv_path": csv_path,
        "rows": len(df),
        "duration_sec": round(duration, 2),
        "global_metrics": global_result["metrics"],
        "global_importance": global_result["importance"],
        "per_type_metrics": per_type_metrics,
        "per_region_metrics": per_region_metrics,
        "combined_metrics": combined_metrics,
        "per_type_count": len(per_type_models),
        "used_features": global_num + global_cat,
        "per_type_features": per_type_feature_usage,
        "data_preparation": data_preparation,
        "segment_diagnostics": segment_diagnostics,
        "model_type": "HistGradientBoostingRegressor",
    }


def load_model() -> dict | None:
    """Load model artifact, auto-reloading when the file changes on disk.

    The ARQ worker trains in a separate process, so `invalidate_model_cache()`
    only clears the worker's cache. This mtime check ensures the API process
    picks up the new model without requiring a restart.
    """
    global _model_cache, _model_cache_mtime
    model_path = os.path.join(MODEL_DIR, "price_model.joblib")
    if not os.path.exists(model_path):
        return None
    current_mtime = os.path.getmtime(model_path)
    if _model_cache is not None and current_mtime == _model_cache_mtime:
        return _model_cache
    _model_cache = joblib.load(model_path)
    _model_cache_mtime = current_mtime
    return _model_cache


def invalidate_model_cache() -> None:
    """Clear the in-process model cache (call after training a new model)."""
    global _model_cache, _model_cache_mtime
    _model_cache = None
    _model_cache_mtime = 0.0


def _coerce_binary(value: Any, default: int = 0) -> int:
    """Coerce a value to a binary 0/1 flag."""
    if value is None:
        return default
    if isinstance(value, float) and np.isnan(value):
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, str):
        low = value.strip().lower()
        if low in {"1", "true", "yes", "da"}:
            return 1
        if low in {"0", "false", "no", "ne", ""}:
            return 0
    try:
        fval = float(value)
        if np.isnan(fval):
            return default
        return 1 if fval > 0 else 0
    except (TypeError, ValueError):
        return default


def _build_normalized_payload(
    payload: dict[str, Any],
    numeric_features: list[str],
    categorical_features: list[str],
    artifact: dict[str, Any],
) -> dict[str, Any]:
    """Build a normalized input row for prediction, including derived features and imputation."""
    from app.services.regions_service import lookup_region, normalize

    coords_by_muni = artifact.get("coords_by_municipality", {})
    region_medians = artifact.get("region_medians", {})
    type_medians = artifact.get("type_medians", {})
    global_median = artifact.get("global_median_ppm2", 2000.0)

    row: dict[str, Any] = {}

    # Numeric features
    for col in numeric_features:
        val = payload.get(col)
        if val is None or (isinstance(val, float) and np.isnan(val)):
            row[col] = np.nan
        else:
            try:
                row[col] = float(val)
            except (TypeError, ValueError):
                row[col] = np.nan

    # Categorical features
    for col in categorical_features:
        if col == "municipality_normalized":
            row[col] = normalize_municipality_name(payload.get("municipality"))
            continue
        if col == "statistical_region" and col not in payload:
            muni = normalize_municipality_name(payload.get("municipality"))
            row[col] = lookup_region(muni)
        else:
            val = payload.get(col, "unknown")
            row[col] = normalize(str(val)) if val else "unknown"

    # Derived: building_age
    if "building_age" in numeric_features and "building_age" not in payload:
        yb = payload.get("year_built")
        if yb is not None and not (isinstance(yb, float) and np.isnan(yb)):
            row["building_age"] = float(pd.Timestamp.now().year - int(yb))
        else:
            row["building_age"] = np.nan

    # Derived: log_size_m2
    if "log_size_m2" in numeric_features and "log_size_m2" not in payload:
        sm2 = payload.get("size_m2")
        if sm2 is not None and not (isinstance(sm2, float) and np.isnan(sm2)):
            row["log_size_m2"] = float(np.log1p(max(0, float(sm2))))
        else:
            row["log_size_m2"] = np.nan

    # Binary flags
    for amenity in (
        "novogradnja",
        "has_klet",
        "has_garaza",
        "has_terasa",
        "has_shramba",
        "has_parking",
        "ddv_vkljucen",
        "stavba_je_dokoncana",
    ):
        if amenity in numeric_features:
            default = 1 if amenity == "stavba_je_dokoncana" else 0
            row[amenity] = float(_coerce_binary(payload.get(amenity, default), default=default))

    # num_prostori
    if "num_prostori" in numeric_features:
        val = payload.get("num_prostori", 0)
        try:
            v = float(val)
            row["num_prostori"] = 0.0 if np.isnan(v) else v
        except (TypeError, ValueError):
            row["num_prostori"] = 0.0

    # transaction_year / transaction_quarter
    if "transaction_year" in numeric_features and "transaction_year" not in payload:
        row["transaction_year"] = float(pd.Timestamp.now().year)
    if "transaction_quarter" in numeric_features and "transaction_quarter" not in payload:
        row["transaction_quarter"] = float(pd.Timestamp.now().quarter)

    # Lat/lon imputation from municipality coords
    municipality_norm = normalize_municipality_name(payload.get("municipality"))
    for coord_key in ("latitude", "longitude"):
        val = row.get(coord_key)
        if val is None or (isinstance(val, float) and np.isnan(val)):
            muni_coords = coords_by_muni.get(municipality_norm, {})
            coord_val = muni_coords.get("lat" if coord_key == "latitude" else "lon")
            if coord_val is None:
                coord_val = muni_coords.get(coord_key)
            row[coord_key] = float(coord_val) if coord_val is not None else np.nan

    # Group medians
    if "price_per_m2_region" in numeric_features:
        region = row.get("statistical_region", "neznana")
        row["price_per_m2_region"] = region_medians.get(region, global_median)

    if "price_per_m2_type" in numeric_features:
        ptype = row.get("property_type", "unknown")
        row["price_per_m2_type"] = type_medians.get(ptype, global_median)

    if "price_per_m2_municipality" in numeric_features:
        municipality_medians = artifact.get("municipality_medians", {})
        muni_key = row.get("municipality_normalized", municipality_norm)
        row["price_per_m2_municipality"] = municipality_medians.get(
            muni_key, region_medians.get(row.get("statistical_region", "neznana"), global_median)
        )

    return row


def predict_one(features: dict[str, Any]) -> dict[str, Any]:
    """Predict price for a single property."""
    artifact = load_model()
    if artifact is None:
        raise RuntimeError("No trained model found. Train a model first.")

    from app.services.regions_service import normalize

    ptype = normalize(str(features.get("property_type", "unknown")))

    # Route to per-type model or global
    per_type_models = artifact.get("per_type_models", {})
    global_model = artifact.get("global_model", {})

    if ptype in per_type_models:
        tm = per_type_models[ptype]
        if isinstance(tm, dict) and "pipeline" in tm:
            pipeline = tm["pipeline"]
            num_feats = tm["numeric_features"]
            cat_feats = tm["categorical_features"]
        else:
            # Legacy: pipeline stored directly
            pipeline = tm
            num_feats = PERTYPE_NUMERIC
            cat_feats = PERTYPE_CATEGORICAL
        model_used = f"per_type:{ptype}"
    elif global_model and "pipeline" in global_model:
        pipeline = global_model["pipeline"]
        num_feats = global_model["numeric_features"]
        cat_feats = global_model["categorical_features"]
        model_used = "global"
    else:
        pipeline = artifact["global_pipeline"]
        num_feats = NUMERIC_FEATURES
        cat_feats = CATEGORICAL_FEATURES
        model_used = "global"

    normalized = _build_normalized_payload(features, num_feats, cat_feats, artifact)
    row = pd.DataFrame([normalized])
    raw_pred = float(pipeline.predict(row)[0])

    # Log-transform: model was trained on log1p(price), so expm1 to get original scale
    predicted = max(0.0, float(np.expm1(raw_pred))) if artifact.get("log_target") else max(0.0, raw_pred)

    return {
        "predicted_price_eur": round(predicted, 2),
        "model_used": model_used,
        "features_used": {k: str(v) for k, v in normalized.items()},
    }


def get_model_info() -> dict[str, Any] | None:
    """Get metadata about the currently loaded model."""
    artifact = load_model()
    if artifact is None:
        return None
    return {
        "version": artifact.get("version"),
        "trained_at": artifact.get("trained_at"),
        "rows": artifact.get("rows"),
        "train_rows": artifact.get("train_rows"),
        "test_rows": artifact.get("test_rows"),
        "used_features": artifact.get("used_features", []),
        "model_type": artifact.get("model_type", "HistGradientBoostingRegressor"),
        "duration_sec": artifact.get("duration_sec"),
        "global_metrics": artifact.get("global_metrics"),
        "per_type_metrics": artifact.get("per_type_metrics"),
        "per_region_metrics": artifact.get("per_region_metrics"),
        "combined_metrics": artifact.get("combined_metrics"),
        "global_importance": artifact.get("global_importance"),
        "feature_labels": artifact.get("feature_labels"),
        "per_type_features": artifact.get("per_type_features"),
        "per_type_count": len(artifact.get("per_type_models", {})),
        "type_models_trained": sorted(artifact.get("per_type_models", {}).keys()),
        "coords_by_municipality": artifact.get("coords_by_municipality"),
        "csv_path": artifact.get("csv_path"),
        "data_preparation": artifact.get("data_preparation"),
        "segment_diagnostics": artifact.get("segment_diagnostics"),
    }
