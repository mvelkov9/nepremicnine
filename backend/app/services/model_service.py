"""Model training & prediction service — HistGradientBoosting per-type architecture."""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import TargetEncoder

from app.services.data_processing_service import (
    EXCLUDED_PROPERTY_TYPES,
    enrich_training_df,
    read_csv_flexible,
)

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
    "uporabna_povrsina",
    "stavba_je_dokoncana",
    "ddv_vkljucen",
    "log_size_m2",
    "transaction_year",
    "price_per_m2_region",
    "price_per_m2_type",
]

CATEGORICAL_FEATURES = [
    "municipality",
    "property_type",
    "statistical_region",
    "lega_v_stavbi",
]

PERTYPE_NUMERIC = [f for f in NUMERIC_FEATURES if f != "price_per_m2_type"]
PERTYPE_CATEGORICAL = [f for f in CATEGORICAL_FEATURES if f != "property_type"]

MIN_SAMPLES_PER_TYPE = 200

FEATURE_LABELS_SL: dict[str, str] = {
    "size_m2": "Velikost (m²)",
    "rooms": "Število sob",
    "year_built": "Leto izgradnje",
    "floor": "Nadstropje",
    "latitude": "GPS širina",
    "longitude": "GPS dolžina",
    "municipality": "Občina",
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
    "uporabna_povrsina": "Uporabna površina",
    "stavba_je_dokoncana": "Stavba dokončana",
    "ddv_vkljucen": "DDV vključen",
    "lega_v_stavbi": "Lega v stavbi",
    "transaction_year": "Leto transakcije",
    "price_per_m2_region": "€/m² regija",
    "price_per_m2_type": "€/m² tip",
}

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "models")


def _adaptive_hyperparams(n_samples: int) -> dict:
    if n_samples > 5000:
        return {"max_iter": 1500, "learning_rate": 0.03, "max_depth": 8}
    if n_samples > 1000:
        return {"max_iter": 1000, "learning_rate": 0.04, "max_depth": 7}
    return {"max_iter": 600, "learning_rate": 0.05, "max_depth": 6}


def _build_pipeline(
    numeric_feats: list[str],
    categorical_feats: list[str],
    n_samples: int,
    y_train: np.ndarray | None = None,
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
    model = HistGradientBoostingRegressor(
        max_iter=hp["max_iter"],
        learning_rate=hp["learning_rate"],
        max_depth=hp["max_depth"],
        min_samples_leaf=20,
        max_bins=255,
        l2_regularization=0.1,
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


def _train_single_model(
    pipeline: Pipeline,
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    X_test: pd.DataFrame,
    y_test: np.ndarray,
    label: str,
    progress_callback: Callable | None = None,
) -> dict:
    regressor = pipeline.named_steps["regressor"]
    total_trees = regressor.max_iter
    chunk_size = max(50, total_trees // 20)
    fitted_trees = 0

    while fitted_trees < total_trees:
        next_target = min(fitted_trees + chunk_size, total_trees)
        regressor.max_iter = next_target
        pipeline.fit(X_train, y_train)
        fitted_trees = next_target

        if progress_callback:
            progress_callback(label, fitted_trees, total_trees)

    y_pred = pipeline.predict(X_test)
    metrics = _compute_metrics(y_test, y_pred)
    metrics["n_train"] = len(X_train)
    metrics["n_test"] = len(X_test)

    importance = {}
    try:
        feat_names = pipeline.named_steps["preprocessor"].get_feature_names_out()
        importances = regressor.feature_importances_
        importance = dict(zip([str(n) for n in feat_names], [float(v) for v in importances], strict=False))
    except Exception:
        pass

    return {"metrics": metrics, "importance": importance}


def train_from_csv(
    csv_path: str,
    progress_callback: Callable | None = None,
) -> dict[str, Any]:
    """Train per-type + global models from a training CSV. Returns model metadata."""
    start = time.time()
    df = read_csv_flexible(csv_path)
    df = enrich_training_df(df)

    # Clean price
    df["price_eur"] = pd.to_numeric(df.get("price_eur"), errors="coerce")
    df = df.dropna(subset=["price_eur"])
    df = df[df["price_eur"] > 0]

    # Exclude non-predictable types
    if "property_type" in df.columns:
        df = df[~df["property_type"].isin(EXCLUDED_PROPERTY_TYPES)]

    # Group medians for price_per_m2
    df["size_m2"] = pd.to_numeric(df.get("size_m2"), errors="coerce")
    valid = df[df["size_m2"] > 0].copy()
    valid["ppm2"] = valid["price_eur"] / valid["size_m2"]

    region_medians = (
        valid.groupby("statistical_region")["ppm2"].median().to_dict() if "statistical_region" in valid.columns else {}
    )
    type_medians = valid.groupby("property_type")["ppm2"].median().to_dict() if "property_type" in valid.columns else {}

    global_median_ppm2 = float(valid["ppm2"].median()) if len(valid) > 0 else 2000.0
    df["price_per_m2_region"] = df.get("statistical_region", pd.Series()).map(region_medians).fillna(global_median_ppm2)
    df["price_per_m2_type"] = df.get("property_type", pd.Series()).map(type_medians).fillna(global_median_ppm2)

    y = df["price_eur"].values
    X = df.drop(columns=["price_eur"], errors="ignore")

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Global model
    global_pipeline = _build_pipeline(NUMERIC_FEATURES, CATEGORICAL_FEATURES, len(X_train))
    global_result = _train_single_model(
        global_pipeline,
        X_train,
        y_train,
        X_test,
        y_test,
        "global",
        progress_callback,
    )

    # Per-type models
    per_type_models: dict[str, Pipeline] = {}
    per_type_metrics: dict[str, dict] = {}

    if "property_type" in X_train.columns:
        type_counts = X_train["property_type"].value_counts()
        eligible = type_counts[type_counts >= MIN_SAMPLES_PER_TYPE].index.tolist()

        for ptype in eligible:
            mask_train = X_train["property_type"] == ptype
            mask_test = X_test["property_type"] == ptype
            Xt = X_train[mask_train]
            yt = y_train[mask_train]
            Xte = X_test[mask_test]
            yte = y_test[mask_test]

            if len(Xte) < 10:
                continue

            pt_pipeline = _build_pipeline(PERTYPE_NUMERIC, PERTYPE_CATEGORICAL, len(Xt))
            pt_result = _train_single_model(
                pt_pipeline,
                Xt,
                yt,
                Xte,
                yte,
                f"type:{ptype}",
                progress_callback,
            )
            per_type_models[ptype] = pt_pipeline
            per_type_metrics[ptype] = pt_result["metrics"]

    # Per-region metrics (not separate models)
    per_region_metrics: dict[str, dict] = {}
    if "statistical_region" in X_test.columns:
        y_pred_all = global_pipeline.predict(X_test)
        for region in X_test["statistical_region"].unique():
            mask = X_test["statistical_region"] == region
            if mask.sum() >= 10:
                per_region_metrics[str(region)] = _compute_metrics(y_test[mask], y_pred_all[mask])

    # Municipality coordinates
    coords_by_municipality: dict[str, dict] = {}
    for col_pair in [("municipality", "latitude", "longitude")]:
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
    artifact = {
        "version": "2.0",
        "global_pipeline": global_pipeline,
        "per_type_models": per_type_models,
        "region_medians": region_medians,
        "type_medians": type_medians,
        "global_median_ppm2": global_median_ppm2,
        "global_metrics": global_result["metrics"],
        "global_importance": global_result["importance"],
        "per_type_metrics": per_type_metrics,
        "per_region_metrics": per_region_metrics,
        "coords_by_municipality": coords_by_municipality,
        "feature_labels": FEATURE_LABELS_SL,
        "trained_at": pd.Timestamp.now().isoformat(),
        "csv_path": csv_path,
        "rows": len(df),
        "duration_sec": duration,
    }
    model_path = os.path.join(MODEL_DIR, "price_model.joblib")
    joblib.dump(artifact, model_path, compress=3)

    return {
        "model_path": model_path,
        "rows": len(df),
        "duration_sec": round(duration, 2),
        "global_metrics": global_result["metrics"],
        "global_importance": global_result["importance"],
        "per_type_metrics": per_type_metrics,
        "per_region_metrics": per_region_metrics,
        "per_type_count": len(per_type_models),
    }


def load_model() -> dict | None:
    model_path = os.path.join(MODEL_DIR, "price_model.joblib")
    if not os.path.exists(model_path):
        return None
    return joblib.load(model_path)


def predict_one(features: dict[str, Any]) -> dict[str, Any]:
    """Predict price for a single property."""
    artifact = load_model()
    if artifact is None:
        raise RuntimeError("No trained model found. Train a model first.")

    # Prepare input
    row = pd.DataFrame([features])
    row = enrich_training_df(row)

    # Add group medians
    region_medians = artifact.get("region_medians", {})
    type_medians = artifact.get("type_medians", {})
    global_median = artifact.get("global_median_ppm2", 2000.0)

    region = row.get("statistical_region", pd.Series(["unknown"])).iloc[0]
    ptype = row.get("property_type", pd.Series(["unknown"])).iloc[0]
    row["price_per_m2_region"] = region_medians.get(region, global_median)
    row["price_per_m2_type"] = type_medians.get(ptype, global_median)

    # Route to per-type model or fallback to global
    per_type_models = artifact.get("per_type_models", {})
    if ptype in per_type_models:
        pipeline = per_type_models[ptype]
        model_used = f"per_type:{ptype}"
    else:
        pipeline = artifact["global_pipeline"]
        model_used = "global"

    predicted = float(pipeline.predict(row)[0])

    return {
        "predicted_price_eur": round(predicted, 2),
        "model_used": model_used,
        "features_used": features,
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
        "duration_sec": artifact.get("duration_sec"),
        "global_metrics": artifact.get("global_metrics"),
        "per_type_metrics": artifact.get("per_type_metrics"),
        "per_region_metrics": artifact.get("per_region_metrics"),
        "global_importance": artifact.get("global_importance"),
        "feature_labels": artifact.get("feature_labels"),
        "per_type_count": len(artifact.get("per_type_models", {})),
        "coords_by_municipality": artifact.get("coords_by_municipality"),
    }
