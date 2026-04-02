from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from app.services.data_processing_service import (
    discover_etn_kpp_year_pairs,
    load_training_metadata,
    prepare_training_csv_from_etn_kpp_bulk,
)
from app.services.model_service import _get_catboost_task_type, train_from_csv

DEFAULT_START_YEARS = [2020, 2018, 2016, 2014, 2012, 2010, 2007]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _combined_metrics(result: dict[str, Any]) -> dict[str, Any]:
    return dict(result.get("combined_metrics") or {})


def _major_type_snapshot(result: dict[str, Any]) -> dict[str, dict[str, float | None]]:
    per_type = result.get("per_type_metrics") or {}
    snapshot: dict[str, dict[str, float | None]] = {}
    for property_type in ("stanovanje", "hisa", "parcela", "kmetijsko"):
        metrics = per_type.get(property_type) or {}
        snapshot[property_type] = {
            "r2": metrics.get("r2"),
            "mape": metrics.get("mape"),
        }
    return snapshot


def _score_signature(result: dict[str, Any]) -> dict[str, Any]:
    combined = _combined_metrics(result)
    return {
        "r2": combined.get("r2"),
        "mape": combined.get("mape"),
        "mae": combined.get("mae"),
        "rmse": combined.get("rmse"),
        "major_types": _major_type_snapshot(result),
    }


def _major_types_hold(candidate: dict[str, Any], incumbent: dict[str, Any]) -> bool:
    candidate_major = _major_type_snapshot(candidate)
    incumbent_major = _major_type_snapshot(incumbent)
    for property_type in ("stanovanje", "hisa"):
        cand = candidate_major.get(property_type) or {}
        inc = incumbent_major.get(property_type) or {}
        cand_r2 = cand.get("r2")
        inc_r2 = inc.get("r2")
        cand_mape = cand.get("mape")
        inc_mape = inc.get("mape")
        if isinstance(cand_r2, (int, float)) and isinstance(inc_r2, (int, float)) and cand_r2 < inc_r2 - 0.03:
            return False
        if isinstance(cand_mape, (int, float)) and isinstance(inc_mape, (int, float)) and cand_mape > inc_mape + 4.0:
            return False
    return True


def _is_better(candidate: dict[str, Any], incumbent: dict[str, Any] | None) -> bool:
    if incumbent is None:
        return True

    candidate_combined = _combined_metrics(candidate)
    incumbent_combined = _combined_metrics(incumbent)
    candidate_r2 = candidate_combined.get("r2")
    incumbent_r2 = incumbent_combined.get("r2")
    candidate_mape = candidate_combined.get("mape")
    incumbent_mape = incumbent_combined.get("mape")
    if not isinstance(candidate_r2, (int, float)) or not isinstance(candidate_mape, (int, float)):
        return False
    if not isinstance(incumbent_r2, (int, float)) or not isinstance(incumbent_mape, (int, float)):
        return True
    if not _major_types_hold(candidate, incumbent):
        return False

    clearly_better_mape = candidate_mape < incumbent_mape - 0.4 and candidate_r2 >= incumbent_r2 - 0.01
    clearly_better_r2 = candidate_r2 > incumbent_r2 + 0.01 and candidate_mape <= incumbent_mape + 0.75
    balanced_gain = candidate_mape < incumbent_mape - 0.15 and candidate_r2 > incumbent_r2 + 0.002
    return clearly_better_mape or clearly_better_r2 or balanced_gain


def _experiment_plan(end_year: int) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    for start_year in DEFAULT_START_YEARS:
        benchmark = start_year >= 2016
        plan.append(
            {
                "label": f"{start_year}_{end_year}",
                "start_year": start_year,
                "end_year": end_year,
                "benchmark_per_type_variants": benchmark,
            }
        )
    return plan


def _prepare_summary(output_csv: Path, prepare_result: dict[str, Any]) -> dict[str, Any]:
    metadata = load_training_metadata(str(output_csv)) or {}
    return {
        "output_csv_path": str(output_csv),
        "rows": prepare_result.get("rows"),
        "pairs_used": prepare_result.get("pairs_used"),
        "pairs_received": prepare_result.get("pairs_received"),
        "deduplicated_rows": prepare_result.get("deduplicated_rows"),
        "per_year": prepare_result.get("per_year"),
        "metadata_summary": {
            "rows": metadata.get("rows"),
            "pairs_used": metadata.get("pairs_used"),
            "per_year": metadata.get("per_year"),
        },
    }


def _run_experiment(
    experiment: dict[str, Any],
    *,
    upload_dir: Path,
    output_root: Path,
    dry_run: bool,
) -> dict[str, Any]:
    start_year = int(experiment["start_year"])
    end_year = int(experiment["end_year"])
    label = str(experiment["label"])
    benchmark = bool(experiment["benchmark_per_type_variants"])
    run_dir = output_root / label
    csv_path = output_root / "prepared" / f"train_{start_year}_{end_year}.csv"
    model_path = run_dir / f"price_model_{start_year}_{end_year}.joblib"
    diagnostics_path = run_dir / f"per_type_diagnostics_{start_year}_{end_year}.json"
    summary_path = run_dir / f"summary_{start_year}_{end_year}.json"
    prepare_path = run_dir / f"prepare_{start_year}_{end_year}.json"

    if dry_run:
        return {
            "label": label,
            "start_year": start_year,
            "end_year": end_year,
            "dry_run": True,
            "csv_path": str(csv_path),
            "model_path": str(model_path),
            "benchmark_per_type_variants": benchmark,
        }

    pairs = discover_etn_kpp_year_pairs(
        str(upload_dir),
        start_year=start_year,
        end_year=end_year,
    )
    if not pairs:
        raise RuntimeError(f"No ETN KPP pairs found for {start_year}-{end_year}")

    prepare_result = prepare_training_csv_from_etn_kpp_bulk(
        pairs,
        str(csv_path),
        enrichment_options={
            "enable_rn": True,
            "enable_ev": True,
            "enable_kn": True,
            "enable_gji": True,
            "enable_emv": True,
            "variant_label": f"research_queue_{label}",
        },
    )
    prepare_summary = _prepare_summary(csv_path, prepare_result)
    _write_json(prepare_path, prepare_summary)

    train_result = train_from_csv(
        str(csv_path),
        model_output_path=str(model_path),
        artifact_metadata={
            "variant_label": f"research_queue_{label}",
            "research_mode": True,
            "enable_market_validity_filter": True,
            "dataset_window": {"start_year": start_year, "end_year": end_year},
            "queue_label": label,
            "task_type": _get_catboost_task_type(),
        },
        allowed_sale_types={"1"},
        benchmark_per_type_variants=benchmark,
    )

    diagnostics_payload = train_result.get("recent_research_diagnostics") or {}
    diagnostics_payload["routing_comparison"] = train_result.get("routing_comparison")
    diagnostics_payload["per_type_features"] = train_result.get("per_type_features")
    diagnostics_payload["dataset_window"] = train_result.get("dataset_window")
    _write_json(diagnostics_path, diagnostics_payload)

    summary_payload = {
        "label": label,
        "start_year": start_year,
        "end_year": end_year,
        "benchmark_per_type_variants": benchmark,
        "task_type": _get_catboost_task_type(),
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
        },
        "score_signature": _score_signature(train_result),
    }
    _write_json(summary_path, summary_payload)
    return summary_payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timebox-hours", type=float, default=24.0)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--upload-dir", default="data/uploads")
    parser.add_argument("--output-root", default="data/models/research_queue")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    started_at = time.time()
    deadline = started_at + max(args.timebox_hours, 0.0) * 3600
    upload_dir = Path(args.upload_dir).resolve()
    output_root = Path(args.output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    leaderboard_path = output_root / "leaderboard.json"
    state_path = output_root / "state.json"

    leaderboard: list[dict[str, Any]] = _read_json(leaderboard_path) or []
    state = _read_json(state_path) or {}
    incumbent_summary: dict[str, Any] | None = None
    if state.get("best_summary_path"):
        incumbent_summary = _read_json(Path(str(state["best_summary_path"])))

    plan = _experiment_plan(args.end_year)
    for experiment in plan:
        now = time.time()
        if now >= deadline:
            break

        label = str(experiment["label"])
        run_state = {
            "status": "running",
            "label": label,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "timebox_hours": args.timebox_hours,
            "task_type": _get_catboost_task_type(),
            "best_summary_path": state.get("best_summary_path"),
        }
        _write_json(state_path, run_state)
        experiment_started = time.time()
        try:
            summary = _run_experiment(
                experiment,
                upload_dir=upload_dir,
                output_root=output_root,
                dry_run=args.dry_run,
            )
        except Exception as exc:
            failure_entry = {
                "label": label,
                "summary_path": None,
                "elapsed_sec": round(time.time() - experiment_started, 2),
                "dry_run": args.dry_run,
                "score_signature": None,
                "benchmark_per_type_variants": experiment["benchmark_per_type_variants"],
                "is_best": False,
                "failed": True,
                "error": str(exc),
            }
            leaderboard.append(failure_entry)
            _write_json(leaderboard_path, {"runs": leaderboard})
            state.update(
                {
                    "status": "running",
                    "last_failed_label": label,
                    "last_failed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "last_error": str(exc),
                    "leaderboard_path": str(leaderboard_path),
                    "task_type": _get_catboost_task_type(),
                    "seconds_remaining": max(int(deadline - time.time()), 0),
                }
            )
            _write_json(state_path, state)
            continue
        elapsed_sec = round(time.time() - experiment_started, 2)

        summary_path = output_root / label / f"summary_{experiment['start_year']}_{experiment['end_year']}.json"
        if args.dry_run:
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            _write_json(summary_path, summary)

        candidate_result = {"combined_metrics": (summary.get("train") or {}).get("combined_metrics", {})}
        if args.dry_run:
            is_best = False
        else:
            incumbent_result = None
            if incumbent_summary is not None:
                incumbent_result = {
                    "combined_metrics": (incumbent_summary.get("train") or {}).get("combined_metrics", {})
                }
                incumbent_result["per_type_metrics"] = (incumbent_summary.get("train") or {}).get(
                    "per_type_metrics", {}
                )
            candidate_result["per_type_metrics"] = (summary.get("train") or {}).get("per_type_metrics", {})
            is_best = _is_better(candidate_result, incumbent_result)

        leaderboard_entry = {
            "label": label,
            "summary_path": str(summary_path),
            "elapsed_sec": elapsed_sec,
            "dry_run": args.dry_run,
            "score_signature": summary.get("score_signature"),
            "benchmark_per_type_variants": experiment["benchmark_per_type_variants"],
            "is_best": is_best,
        }
        leaderboard.append(leaderboard_entry)
        _write_json(leaderboard_path, {"runs": leaderboard})

        if is_best and not args.dry_run:
            incumbent_summary = summary
            state["best_summary_path"] = str(summary_path)
            state["best_label"] = label

        state.update(
            {
                "status": "running",
                "last_completed_label": label,
                "last_completed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "best_summary_path": state.get("best_summary_path"),
                "best_label": state.get("best_label"),
                "leaderboard_path": str(leaderboard_path),
                "task_type": _get_catboost_task_type(),
                "seconds_remaining": max(int(deadline - time.time()), 0),
            }
        )
        _write_json(state_path, state)

    state.update(
        {
            "status": "finished" if time.time() < deadline else "timebox_reached",
            "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "leaderboard_path": str(leaderboard_path),
            "task_type": _get_catboost_task_type(),
        }
    )
    _write_json(state_path, state)
    print(json.dumps(state, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
