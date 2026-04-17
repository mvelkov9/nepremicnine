from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services.data_processing_service import load_training_metadata, prepare_training_csv_from_etn_kpp_bulk
from app.services.model_service import train_from_csv


def _build_pairs(upload_dir: Path, start_year: int, end_year: int) -> list[dict[str, str]]:
    pairs: list[dict[str, str]] = []
    for year in range(start_year, end_year + 1):
        year_s = str(year)
        posli = next(upload_dir.glob(f"**/*ETN_SLO_{year_s}_KPP_KPP_POSLI_*.csv"))
        deli = next(upload_dir.glob(f"**/*ETN_SLO_{year_s}_KPP_KPP_DELISTAVB_*.csv"))
        zem = next(upload_dir.glob(f"**/*ETN_SLO_{year_s}_KPP_KPP_ZEMLJISCA_*.csv"))
        pairs.append(
            {
                "posli_csv_path": str(posli),
                "delistavb_csv_path": str(deli),
                "zemljisca_csv_path": str(zem),
                "year": year_s,
                "label": year_s,
            }
        )
    return pairs


def _summarize_prepare(output_csv: Path, result: dict) -> dict:
    metadata = load_training_metadata(str(output_csv)) or {}
    reports = metadata.get("reports") or []
    enrichment_years = metadata.get("enrichment_summary", {}).get("years", {})
    return {
        "rows": result.get("rows"),
        "pairs_used": result.get("pairs_used"),
        "deduplicated_rows": result.get("deduplicated_rows"),
        "per_year": result.get("per_year"),
        "variant_label": result.get("enrichment_options", {}).get("variant_label"),
        "report_count": len(reports),
        "enrichment_years": sorted(enrichment_years.keys()),
        "output_csv_path": str(output_csv),
    }


def _summarize_train(result: dict) -> dict:
    variant_matrix = result.get("variant_matrix") or {}
    return {
        "rows": result.get("rows"),
        "duration_sec": result.get("duration_sec"),
        "model_path": result.get("model_path"),
        "global_metrics": result.get("global_metrics"),
        "combined_metrics": result.get("combined_metrics"),
        "ev_baseline_metrics": result.get("ev_baseline_metrics"),
        "variant_matrix_keys": sorted(variant_matrix.keys()),
        "variant_matrix": {
            key: {
                "variant_label": value.get("variant_label"),
                "enabled_sources": value.get("enabled_sources"),
                "global_metrics": value.get("global_metrics"),
                "combined_metrics": value.get("combined_metrics"),
                "per_type_count": value.get("per_type_count"),
            }
            for key, value in variant_matrix.items()
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--start-year", type=int, default=2020)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--upload-dir", default="/app/data/uploads")
    parser.add_argument("--output-csv", default="/app/data/raw/train.csv")
    args = parser.parse_args()

    upload_dir = Path(args.upload_dir)
    output_csv = Path(args.output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    pairs = _build_pairs(upload_dir, args.start_year, args.end_year)
    prepare_result = prepare_training_csv_from_etn_kpp_bulk(
        pairs,
        str(output_csv),
        enrichment_options={
            "enable_rn": True,
            "enable_ev": True,
            "enable_kn": True,
            "enable_gji": True,
            "enable_dtm": True,
            "enable_emv": True,
            "variant_label": "rn+ev+kn+gji+emv",
        },
    )

    payload: dict[str, object] = {
        "prepare": _summarize_prepare(output_csv, prepare_result),
    }

    if not args.prepare_only:
        train_result = train_from_csv(str(output_csv))
        payload["train"] = _summarize_train(train_result)

    print(json.dumps(payload, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
