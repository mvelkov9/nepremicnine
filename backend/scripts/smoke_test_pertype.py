"""Tiny sanity test: fit a CatBoost per-type model on parcela data only,
with a few iterations, to verify the per-type path is not broken before
kicking off a multi-hour full training run."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from app.services.model_service import (  # noqa: E402
    CatBoostModel,
    _adaptive_hyperparams,
    _get_catboost_task_type,
)

CSV_PATH = ROOT / "data" / "raw" / "train_2020_2026.csv"

print(f"Task type: {_get_catboost_task_type()}")
print(f"Loading a small slice from {CSV_PATH} ...")
# Use chunking to avoid loading the whole 173MB for a smoke test
usecols = None
df = pd.read_csv(CSV_PATH, nrows=50_000, low_memory=False)
print(f"Loaded {len(df)} rows, {len(df.columns)} columns")

# Filter to parcela only
df = df[df["property_type"] == "parcela"].copy()
print(f"After filter to parcela: {len(df)} rows")

if len(df) < 500:
    print("Not enough parcela rows in the first 50k; expanding...")
    df = pd.read_csv(CSV_PATH, low_memory=False)
    df = df[df["property_type"] == "parcela"].head(10_000).copy()
    print(f"Expanded: {len(df)} rows")

# Prepare minimal targets
if "price_eur" not in df.columns:
    print("ERROR: 'price_eur' column missing")
    sys.exit(1)

y = df["price_eur"].astype(float).values
df = df.drop(columns=["price_eur"])

# Use a handful of numeric features
num_features = [c for c in ["size_m2", "parcela_area", "lon", "lat", "year_built"] if c in df.columns]
cat_features = [c for c in ["naselje", "municipality_normalized", "ime_ko"] if c in df.columns]
print(f"Using num={num_features} cat={cat_features}")

X = df[num_features + cat_features].copy()
for c in cat_features:
    X[c] = X[c].fillna("__NA__").astype(str)
for c in num_features:
    X[c] = pd.to_numeric(X[c], errors="coerce").fillna(0.0)

# Train/test split
split = int(0.8 * len(X))
X_tr, X_te = X.iloc[:split], X.iloc[split:]
y_tr_raw, y_te_raw = y[:split], y[split:]

# log_price transform (matches parcela baseline target)
y_tr = np.log1p(np.clip(y_tr_raw, 1.0, None))
y_te = np.log1p(np.clip(y_te_raw, 1.0, None))

print(f"y_tr log_price: min={y_tr.min():.2f} max={y_tr.max():.2f} mean={y_tr.mean():.2f} std={y_tr.std():.2f}")

hp = _adaptive_hyperparams(len(X_tr))
# Shrink for smoke test
hp["iterations"] = 200
hp["od_wait"] = 50
print(f"HP: loss={hp.get('loss_function')}, task_type={hp.get('task_type')}, "
      f"iterations={hp['iterations']}, depth={hp.get('depth')}, lr={hp.get('learning_rate')}")

model = CatBoostModel(
    numeric_features=num_features,
    categorical_features=cat_features,
    params=hp,
)

t0 = time.time()
model.fit(X_tr, y_tr, X_eval=X_te, y_eval=y_te, label="smoke_parcela")
elapsed = time.time() - t0

y_pred_log = model.predict(X_te)
y_pred = np.expm1(np.clip(y_pred_log, -30, 30))

# Metrics
from sklearn.metrics import mean_absolute_percentage_error, r2_score  # noqa: E402

r2 = r2_score(y_te_raw, y_pred)
mape = mean_absolute_percentage_error(y_te_raw, y_pred) * 100
print("\n=== SMOKE RESULT ===")
print(f"best_iteration: {getattr(model.model, 'best_iteration_', 'n/a')}")
print(f"tree_count: {getattr(model.model, 'tree_count_', 'n/a')}")
print(f"Elapsed: {elapsed:.1f}s")
print(f"R2: {r2:.4f}")
print(f"MAPE: {mape:.1f}%")
print(f"y_pred sample: {y_pred[:5]}")
print(f"y_true sample: {y_te_raw[:5]}")
