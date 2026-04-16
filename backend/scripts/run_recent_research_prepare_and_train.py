from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.services.data_processing_service import (
    discover_etn_kpp_year_pairs,
    load_training_metadata,
    prepare_training_csv_from_etn_kpp_bulk,
)
from app.services.model_service import get_model_info, train_from_csv


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _summarize_prepare(output_csv: Path, result: dict[str, Any]) -> dict[str, Any]:
    metadata = load_training_metadata(str(output_csv)) or {}
    return {
        "output_csv_path": str(output_csv),
        "rows": result.get("rows"),
        "pairs_used": result.get("pairs_used"),
        "pairs_received": result.get("pairs_received"),
        "deduplicated_rows": result.get("deduplicated_rows"),
        "per_year": result.get("per_year"),
        "reports": result.get("reports"),
        "enrichment_options": result.get("enrichment_options"),
        "metadata_summary": {
            "source": metadata.get("source"),
            "rows": metadata.get("rows"),
            "pairs_used": metadata.get("pairs_used"),
            "per_year": metadata.get("per_year"),
        },
    }


def _metric_delta(current: dict[str, Any] | None, baseline: dict[str, Any] | None) -> dict[str, Any] | None:
    if not current or not baseline:
        return None
    delta: dict[str, Any] = {}
    for key in ("r2", "mape", "mae", "rmse", "median_ae"):
        cur = current.get(key)
        base = baseline.get(key)
        if isinstance(cur, (int, float)) and isinstance(base, (int, float)):
            delta[key] = round(float(cur) - float(base), 6)
    return delta or None


def _build_baseline_comparison(recent_result: dict[str, Any], baseline_model_path: Path) -> dict[str, Any]:
    baseline_info = get_model_info(str(baseline_model_path))
    if baseline_info is None:
        return {
            "baseline_model_path": str(baseline_model_path),
            "baseline_available": False,
        }

    recent_per_type = recent_result.get("per_type_metrics") or {}
    baseline_per_type = baseline_info.get("per_type_metrics") or {}
    per_type_comparison: dict[str, Any] = {}
    for property_type in sorted(set(recent_per_type) | set(baseline_per_type)):
        per_type_comparison[property_type] = {
            "recent": recent_per_type.get(property_type),
            "baseline": baseline_per_type.get(property_type),
            "delta": _metric_delta(recent_per_type.get(property_type), baseline_per_type.get(property_type)),
        }

    return {
        "baseline_model_path": str(baseline_model_path),
        "baseline_available": True,
        "baseline_dataset_window": baseline_info.get("dataset_window") or baseline_info.get("training_window"),
        "baseline_combined_metrics": baseline_info.get("combined_metrics"),
        "recent_combined_metrics": recent_result.get("combined_metrics"),
        "combined_delta": _metric_delta(recent_result.get("combined_metrics"), baseline_info.get("combined_metrics")),
        "baseline_global_metrics": baseline_info.get("global_metrics"),
        "recent_global_metrics": recent_result.get("global_metrics"),
        "global_delta": _metric_delta(recent_result.get("global_metrics"), baseline_info.get("global_metrics")),
        "per_type": per_type_comparison,
    }


def _build_summary(
    *,
    variant_label: str,
    start_year: int,
    end_year: int,
    prepare_summary: dict[str, Any],
    train_result: dict[str, Any],
    baseline_comparison: dict[str, Any],
) -> dict[str, Any]:
    recent_diag = train_result.get("recent_research_diagnostics") or {}
    major_types_ok = {}
    for property_type in ("stanovanje", "hisa"):
        metrics = (train_result.get("per_type_metrics") or {}).get(property_type) or {}
        major_types_ok[property_type] = {
            "r2": metrics.get("r2"),
            "mape": metrics.get("mape"),
            "pass_live_guardrail": bool(
                isinstance(metrics.get("r2"), (int, float))
                and metrics["r2"] >= 0.7
                and isinstance(metrics.get("mape"), (int, float))
                and metrics["mape"] <= 35
            ),
        }

    return {
        "variant_label": variant_label,
        "dataset_window": {"start_year": start_year, "end_year": end_year},
        "prepare": prepare_summary,
        "train": {
            "model_path": train_result.get("model_path"),
            "csv_path": train_result.get("csv_path"),
            "rows": train_result.get("rows"),
            "dataset_window": train_result.get("dataset_window"),
            "global_metrics": train_result.get("global_metrics"),
            "combined_metrics": train_result.get("combined_metrics"),
            "per_type_metrics": train_result.get("per_type_metrics"),
            "routing_comparison": train_result.get("routing_comparison"),
            "artifact_metadata": train_result.get("artifact_metadata"),
        },
        "baseline_comparison": baseline_comparison,
        "acceptance_checks": {
            "recent_rows_only_in_requested_window": sorted((prepare_summary.get("per_year") or {}).keys())
            == [str(year) for year in range(start_year, end_year + 1)],
            "recent_combined_beats_baseline": bool(
                baseline_comparison.get("baseline_available")
                and isinstance((baseline_comparison.get("combined_delta") or {}).get("r2"), (int, float))
                and baseline_comparison["combined_delta"]["r2"] > 0
            ),
            "major_type_guardrails": major_types_ok,
            "residual_diagnostics_present": bool(recent_diag.get("residual_diagnostics")),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--start-year", type=int, default=2020)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--upload-dir", default="backend/data/uploads")
    parser.add_argument("--output-csv", default="backend/data/raw/train_2020_2026.csv")
    parser.add_argument("--model-path", default="backend/data/models/price_model_2020_2026.joblib")
    parser.add_argument("--summary-path", default="backend/data/models/train_summary_2020_2026.json")
    parser.add_argument("--diagnostics-path", default="backend/data/models/per_type_diagnostics_2020_2026.json")
    parser.add_argument("--prepare-summary-path", default="backend/data/models/prepare_2020_2026.json")
    parser.add_argument("--variant-label", default="recent_only_2020_2026")
    parser.add_argument("--baseline-model-path", default="backend/data/models/price_model.joblib")
    args = parser.parse_args()

    output_csv = Path(args.output_csv).resolve()
    model_path = Path(args.model_path).resolve()
    summary_path = Path(args.summary_path).resolve()
    diagnostics_path = Path(args.diagnostics_path).resolve()
    prepare_summary_path = Path(args.prepare_summary_path).resolve()
    baseline_model_path = Path(args.baseline_model_path).resolve()

    pairs = discover_etn_kpp_year_pairs(
        args.upload_dir,
        start_year=args.start_year,
        end_year=args.end_year,
    )
    if not pairs:
        raise SystemExit(f"No ETN KPP pairs found for years {args.start_year}-{args.end_year}")

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
            "variant_label": args.variant_label,
        },
    )
    prepare_summary = _summarize_prepare(output_csv, prepare_result)
    _write_json(prepare_summary_path, prepare_summary)

    if args.prepare_only:
        print(json.dumps({"prepare": prepare_summary}, ensure_ascii=True, indent=2))
        return

    train_result = train_from_csv(
        str(output_csv),
        model_output_path=str(model_path),
        artifact_metadata={
            "variant_label": args.variant_label,
            "research_mode": True,
            "dataset_window": {"start_year": args.start_year, "end_year": args.end_year},
        },
        allowed_sale_types={"1"},
        benchmark_per_type_variants=True,
    )

    diagnostics_payload = train_result.get("recent_research_diagnostics") or {}
    diagnostics_payload["routing_comparison"] = train_result.get("routing_comparison")
    diagnostics_payload["per_type_features"] = train_result.get("per_type_features")
    diagnostics_payload["dataset_window"] = train_result.get("dataset_window")
    _write_json(diagnostics_path, diagnostics_payload)

    baseline_comparison = _build_baseline_comparison(train_result, baseline_model_path)
    summary_payload = _build_summary(
        variant_label=args.variant_label,
        start_year=args.start_year,
        end_year=args.end_year,
        prepare_summary=prepare_summary,
        train_result=train_result,
        baseline_comparison=baseline_comparison,
    )
    _write_json(summary_path, summary_payload)

    print(json.dumps(summary_payload, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
