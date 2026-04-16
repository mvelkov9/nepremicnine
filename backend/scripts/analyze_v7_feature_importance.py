"""Extract per-type feature importance from v7 artifact and identify drag features."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ARTIFACT = ROOT / "data" / "models" / "price_model_optimized_v7.joblib"


def main() -> int:
    print(f"Loading artifact: {ARTIFACT}")
    bundle = joblib.load(ARTIFACT)

    print(f"\nTop-level keys: {list(bundle.keys())[:20]}")

    report: dict = {"per_type": {}, "global": {}}

    # Global model importance
    if "model" in bundle and hasattr(bundle["model"], "get_feature_importance"):
        feat_names = bundle.get("feature_names") or []
        try:
            imp = bundle["model"].get_feature_importance()
            pairs = sorted(zip(feat_names, imp, strict=False), key=lambda x: -x[1])
            report["global"] = {
                "top_20": [(n, float(v)) for n, v in pairs[:20]],
                "bottom_20": [(n, float(v)) for n, v in pairs[-20:]],
                "zero_count": sum(1 for _, v in pairs if v < 0.01),
                "total_count": len(pairs),
            }
        except Exception as e:
            print(f"Global importance failed: {e}")

    # Per-type specialist models
    per_type_models = bundle.get("per_type_models") or {}
    print(f"\nPer-type models found: {list(per_type_models.keys())}")

    for prop_type, type_bundle in per_type_models.items():
        if not isinstance(type_bundle, dict):
            continue
        wrapper = type_bundle.get("pipeline")
        if wrapper is None:
            continue
        model = getattr(wrapper, "model", None)
        if model is None or not hasattr(model, "get_feature_importance"):
            continue
        feat_names = list(getattr(model, "feature_names_", []))
        try:
            imp_raw = model.get_feature_importance()
            imp = [float(v) for v in imp_raw]
            if len(feat_names) != len(imp):
                feat_names = [f"f{i}" for i in range(len(imp))]
            pairs = sorted(zip(feat_names, imp, strict=False), key=lambda x: -x[1])
            total_imp = sum(float(v) for _, v in pairs) or 1.0
            report["per_type"][prop_type] = {
                "n_features": len(pairs),
                "top_15": [(n, float(v), float(v) / total_imp * 100) for n, v in pairs[:15]],
                "drag_features": [
                    (n, float(v), float(v) / total_imp * 100)
                    for n, v in pairs
                    if float(v) < 0.05  # less than 0.05 CatBoost importance = basically noise
                ],
                "zero_count": sum(1 for _, v in pairs if float(v) < 0.05),
                "cumulative_95pct_cutoff": None,
            }
            # Find how many features are needed for 95% cumulative importance
            cum = 0.0
            for i, (_n, v) in enumerate(pairs):
                cum += float(v)
                if cum / total_imp >= 0.95:
                    report["per_type"][prop_type]["cumulative_95pct_cutoff"] = i + 1
                    break
        except Exception as e:
            print(f"[{prop_type}] importance failed: {e}")

    out_path = ROOT / "data" / "models" / "v7_feature_importance.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nWrote: {out_path}")

    print("\n=== SUMMARY ===")
    for prop_type, r in report["per_type"].items():
        print(
            f"\n[{prop_type}] n_features={r['n_features']} drag(imp<0.05)={r['zero_count']} needed_for_95pct={r.get('cumulative_95pct_cutoff')}"
        )
        print("  top 5:", [(n, f"{p:.1f}%") for n, _, p in r["top_15"][:5]])

    return 0


if __name__ == "__main__":
    sys.exit(main())
