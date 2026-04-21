"""Train the v15 production model.

v15 changes vs v13:
  - Tightened MARKET_VALIDITY_RULES: stanovanje min_ppm2 200->500, hisa 120->250,
    poslovni 150->250, turisticni/gostinstvo 150->200, industrijski 80->100
  - Stronger recency sample weights: exponential decay with a 4:1 recent-to-old ratio
  - Tighter per-municipality z-score outlier pass: z>2.0 with min_group=20 (was z>2.5/30)
  - RMSE remains the production loss; Huber is still disabled because GPU experiments
    were unstable and degraded holdout quality

v13 cumulative changes vs v9:
  - Market validity filter for all 9 types
  - Per-municipality z-score outlier pass
  - max_leaves=128 Lossguide for large types (stanovanje, hisa, parcela)
  - 8K iters, LR=0.02, od_wait=300, max_ctr_complexity=2 for large types
  - hp_overrides re-applied after GPU adjustments for correct per-type params
"""

from __future__ import annotations

import json
import sys
import time

from app.services.model_service import train_from_csv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

DATA_DIR = "data"


def main() -> None:
    csv_path = f"{DATA_DIR}/raw/train_2020_2026.csv"
    model_path = f"{DATA_DIR}/models/price_model.joblib"
    summary_path = f"{DATA_DIR}/models/train_summary_latest.json"

    print(f"Starting training from {csv_path}")
    start = time.time()

    result = train_from_csv(
        csv_path,
        model_output_path=model_path,
        artifact_metadata={
            "variant_label": "v15_production",
            "research_mode": False,
            "dataset_window": {"start_year": 2020, "end_year": 2026},
        },
        allowed_sale_types={"1"},
        benchmark_per_type_variants=False,
    )

    duration = time.time() - start
    print(f"Training completed in {duration:.0f}s")
    print(f"Rows: {result.get('rows')}")
    print(f"Model: {result.get('model_path')}")

    global_metrics = result.get("global_metrics") or {}
    print(f"Global R2: {global_metrics.get('r2')}, MAPE: {global_metrics.get('mape')}")

    combined_metrics = result.get("combined_metrics") or {}
    print(f"Combined R2: {combined_metrics.get('r2')}, MAPE: {combined_metrics.get('mape')}")

    for property_type, metrics in (result.get("per_type_metrics") or {}).items():
        print(f"  {property_type}: R2={metrics.get('r2')}, MAPE={metrics.get('mape')}")

    with open(summary_path, "w", encoding="utf-8") as file_handle:
        json.dump(result, file_handle, indent=2, ensure_ascii=False, default=str)
    print(f"Summary written to {summary_path}")


if __name__ == "__main__":
    main()
