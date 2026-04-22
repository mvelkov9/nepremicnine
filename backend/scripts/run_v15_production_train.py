"""Train the v17 production model.

v17 changes vs v16:
  - Price-tier boost applied ONLY to per-type models (not global). Mixing types
    (€10K garaza vs €500K hisa) made "top quartile" meaningless at global scope
    and cost 0.04 R² on the global fallback.
  - poslovni_prostor reverted to log_ppm2 (log_price hurt R² by 0.03).

v16 cumulative:
  - Adaptive z-score: large types z>2.0/min=20, small types (<3000) z>2.5/min=30
  - stanovanje min_ppm2 raised to 700
  - log_price target for stanovanje, hisa specialist models
  - Per-type price-tier sample weighting (top-quartile 1.5x)
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
            "variant_label": "v17_production",
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
