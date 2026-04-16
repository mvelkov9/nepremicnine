"""Quick debug of CatBoost importance format."""

from __future__ import annotations

import sys
from pathlib import Path

import joblib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ARTIFACT = ROOT / "data" / "models" / "price_model_optimized_v7.joblib"

bundle = joblib.load(ARTIFACT)
stan = bundle["per_type_models"]["stanovanje"]
pipeline = stan["pipeline"]

print(f"pipeline type: {type(pipeline)}")
print(f"pipeline attrs: {[a for a in dir(pipeline) if not a.startswith('_')][:30]}")

# CatBoostModel wrapper has .model attr
model = getattr(pipeline, "model", None)
if model is None:
    print("No .model on wrapper")
    sys.exit(1)
print(f"\nUsing inner CatBoost: {type(model).__name__}")

imp = model.get_feature_importance()
print(f"\nimp type: {type(imp)}")
print(f"imp shape/len: {getattr(imp, 'shape', len(imp))}")
print(f"First 5 values: {imp[:5]}")
print(f"Value types: {[type(v).__name__ for v in imp[:3]]}")

# Try to get feature names
print(
    f"\nmodel.feature_names_: {getattr(model, 'feature_names_', 'N/A')[:10] if hasattr(model, 'feature_names_') else 'missing'}"
)

# Numeric + cat
numeric = stan.get("numeric_features") or []
cat = stan.get("categorical_features") or []
print(f"\nnumeric: {len(numeric)}, cat: {len(cat)}, total={len(numeric) + len(cat)}, imp={len(imp)}")
