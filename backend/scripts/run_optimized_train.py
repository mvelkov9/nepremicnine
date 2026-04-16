"""Launch optimized training with explicit logging for diagnostics."""

from __future__ import annotations

import io
import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"optimized_train_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

_stdout_stream = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(_stdout_stream),
    ],
    force=True,
)
logger = logging.getLogger("run_optimized_train")


def main() -> int:
    logger.info("=" * 80)
    logger.info("OPTIMIZED TRAINING LAUNCH")
    logger.info("=" * 80)
    logger.info("CATBOOST_TASK_TYPE=%s", os.environ.get("CATBOOST_TASK_TYPE", "(not set -> CPU)"))
    logger.info("Log file: %s", LOG_FILE)

    try:
        from app.services.model_service import train_from_csv
    except Exception as exc:
        logger.error("Failed to import train_from_csv: %s", exc)
        logger.error(traceback.format_exc())
        return 2

    csv_path = ROOT / "data" / "raw" / "train_2020_2026.csv"
    if not csv_path.exists():
        logger.error("Training CSV not found: %s", csv_path)
        return 3
    logger.info("Training CSV: %s (%.1f MB)", csv_path, csv_path.stat().st_size / 1024 / 1024)

    output_path = ROOT / "data" / "models" / "price_model_optimized_v9.joblib"

    try:
        result = train_from_csv(
            str(csv_path),
            model_output_path=str(output_path),
            artifact_metadata={
                "variant_label": "optimized_v9",
                "research_mode": True,
                "dataset_window": {"start_year": 2020, "end_year": 2026},
                "changes_vs_v8": [
                    "Sub-segmentation: added garaza (by vrsta_dela_stavbe -> aboveground/underground, ~11k/~10k split, 117pp log_ppm2 spread) and hisa (by ev_id_konstrukcija -> brick/concrete/wood/mixed/prefab, 81pp spread) to TYPE_SPECIALIST_MODEL_PRIORS with enable_subtype_family=True",
                    "market_subtype_key now threads vrsta_dela_stavbe and ev_id_konstrukcija for garaza/hisa sub-models via _market_subtype_key_from_values",
                    "Restored wrongly-pruned features from v8 where Spearman |corr| >= 0.15:",
                    "  stanovanje: restored gji_plin_nearby_100m (+0.196), gji_toplota_nearby_100m (+0.189), gji_kanalizacija_nearby_100m (+0.188)",
                    "  hisa: restored gji_plin_nearby_100m (+0.282), prodani_delez_dela_stavbe (+0.239), gji_kanalizacija_nearby_100m (+0.236), novogradnja (+0.161), ddv_vkljucen (+0.159)",
                    "  parcela: restored ALL gji_*_nearby_100m (r=0.44-0.66, biggest miss in v8)",
                    "  kmetijsko: restored gji_plin_nearby_100m (+0.212)",
                    "  garaza: restored ev_ima_kanalizacijo (+0.325), gji_plin_nearby_100m (+0.230), gji_kanalizacija_nearby_100m (+0.210)",
                    "  poslovni_prostor: restored novogradnja (+0.219), prodani_delez_dela_stavbe (+0.170)",
                    "  industrijski: restored novogradnja (+0.277), has_terasa (+0.247), ev_ima_elektriko (+0.227), gji_elektrika_nearby_100m (+0.187), prodani_delez_dela_stavbe (+0.173)",
                    "  gostinstvo: restored gji_plin_nearby_100m (+0.241), novogradnja (+0.194), ev_ima_vodovod (+0.161), gji_kanalizacija_nearby_100m (+0.159), prodani_delez_dela_stavbe (+0.156)",
                    "Added new features to NUMERIC_FEATURES pool: gji_zeleznice_nearby_100m (Spearman 0.12-0.24 across types, preferred over 1000m variant), ev_id_konstrukcija (r=+0.165 stanovanje)",
                ],
            },
            allowed_sale_types={"1"},
            benchmark_per_type_variants=False,
        )
    except Exception as exc:
        logger.error("TRAINING CRASHED: %s", exc)
        logger.error(traceback.format_exc())
        return 4

    logger.info("=" * 80)
    logger.info("TRAINING COMPLETED")
    logger.info("=" * 80)
    logger.info("Result keys: %s", list(result.keys()) if isinstance(result, dict) else type(result))
    if isinstance(result, dict) and "metrics" in result:
        logger.info("Metrics: %s", result["metrics"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
