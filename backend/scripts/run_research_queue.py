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
from app.services.model_service import _get_catboost_task_type, get_model_info, train_from_csv

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


def _metric_delta(current: dict[str, Any] | None, baseline: dict[str, Any] | None) -> dict[str, float]:
    delta: dict[str, float] = {}
    if not current or not baseline:
        return delta
    for key in ("r2", "mape", "mae", "rmse", "median_ae"):
        cur = current.get(key)
        base = baseline.get(key)
        if isinstance(cur, (int, float)) and isinstance(base, (int, float)):
            delta[key] = round(float(cur) - float(base), 6)
    return delta


def _delta_label(delta: dict[str, float]) -> str:
    r2 = delta.get("r2")
    mape = delta.get("mape")
    if isinstance(r2, (int, float)) and isinstance(mape, (int, float)):
        if r2 > 0.01 and mape < -0.2:
            return "helped"
        if r2 < -0.01 and mape > 0.2:
            return "hurt"
        if r2 > 0 or mape < 0:
            return "mixed_positive"
        if r2 < 0 or mape > 0:
            return "mixed_negative"
    return "inconclusive"


def _fmt_metric(value: Any, digits: int = 4) -> str:
    if not isinstance(value, (int, float)):
        return "n/a"
    return f"{float(value):.{digits}f}"


def _load_summary(path_str: str | None) -> dict[str, Any] | None:
    if not path_str:
        return None
    path = Path(path_str)
    return _read_json(path)


def _load_leaderboard(path: Path) -> list[dict[str, Any]]:
    raw = _read_json(path)
    if raw is None:
        return []
    if isinstance(raw, dict):
        runs = raw.get("runs")
        if isinstance(runs, list):
            return [item for item in runs if isinstance(item, dict)]
        return []
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    return []


def _variant_impact(model_info: dict[str, Any]) -> dict[str, Any]:
    variant_matrix = model_info.get("variant_matrix") or {}
    etn_only = (variant_matrix.get("etn_only") or {}).get("combined_metrics") or {}
    deterministic = (variant_matrix.get("deterministic") or {}).get("combined_metrics") or {}
    full_global = (variant_matrix.get("full_global") or {}).get("combined_metrics") or {}
    production_combined = model_info.get("combined_metrics") or {}
    impacts = {
        "rn_ev_kn_vs_etn_only": {
            "delta": _metric_delta(deterministic, etn_only),
        },
        "gji_emv_vs_deterministic": {
            "delta": _metric_delta(full_global, deterministic),
        },
        "per_type_routing_vs_full_global": {
            "delta": _metric_delta(production_combined, full_global),
        },
    }
    for payload in impacts.values():
        payload["verdict"] = _delta_label(payload["delta"])
    return impacts


def _top_feature_rollup(model_info: dict[str, Any], top_n: int = 15) -> list[dict[str, Any]]:
    per_type_features = model_info.get("per_type_features") or {}
    aggregate: dict[str, dict[str, Any]] = {}
    for property_type, info in per_type_features.items():
        top_features = (info or {}).get("top_features") or []
        for rank, item in enumerate(top_features[:10], start=1):
            feature = str(item.get("feature") or "").strip()
            score = item.get("score")
            if not feature or not isinstance(score, (int, float)):
                continue
            bucket = aggregate.setdefault(
                feature,
                {"feature": feature, "occurrences": 0, "score_sum": 0.0, "types": []},
            )
            bucket["occurrences"] += 1
            bucket["score_sum"] += float(score)
            bucket["types"].append({"property_type": property_type, "rank": rank, "score": round(float(score), 6)})

    rolled = []
    for payload in aggregate.values():
        rolled.append(
            {
                "feature": payload["feature"],
                "occurrences": payload["occurrences"],
                "avg_score": round(payload["score_sum"] / max(payload["occurrences"], 1), 6),
                "types": payload["types"],
            }
        )
    rolled.sort(key=lambda item: (-int(item["occurrences"]), -float(item["avg_score"]), str(item["feature"])))
    return rolled[:top_n]


def _low_signal_global_features(model_info: dict[str, Any], top_n: int = 15) -> list[dict[str, Any]]:
    importance = model_info.get("global_importance") or {}
    rows = [
        {"feature": str(feature), "importance": round(float(value), 6)}
        for feature, value in importance.items()
        if isinstance(value, (int, float))
    ]
    rows.sort(key=lambda item: (float(item["importance"]), str(item["feature"])))
    return rows[:top_n]


def _dragging_segments(model_info: dict[str, Any], top_n: int = 6) -> list[dict[str, Any]]:
    per_type = model_info.get("per_type_metrics") or {}
    rows = []
    for property_type, metrics in per_type.items():
        if not isinstance(metrics, dict):
            continue
        r2 = metrics.get("r2")
        mape = metrics.get("mape")
        rows.append(
            {
                "property_type": property_type,
                "r2": round(float(r2), 6) if isinstance(r2, (int, float)) else None,
                "mape": round(float(mape), 6) if isinstance(mape, (int, float)) else None,
                "n_test": metrics.get("n_test"),
            }
        )
    rows.sort(
        key=lambda item: (
            -(float(item["mape"]) if isinstance(item["mape"], (int, float)) else -1.0),
            float(item["r2"]) if isinstance(item["r2"], (int, float)) else 999.0,
        )
    )
    return rows[:top_n]


def _candidate_sort_tuple(candidate: dict[str, Any] | None) -> tuple[float, float, float]:
    metrics = (candidate or {}).get("metrics") or {}
    mape = metrics.get("mape")
    r2 = metrics.get("r2")
    mae = metrics.get("mae")
    return (
        float(mape) if isinstance(mape, (int, float)) else float("inf"),
        -float(r2) if isinstance(r2, (int, float)) else float("inf"),
        float(mae) if isinstance(mae, (int, float)) else float("inf"),
    )


def _best_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    usable = [candidate for candidate in candidates if isinstance(candidate, dict)]
    if not usable:
        return None
    usable.sort(key=_candidate_sort_tuple)
    return usable[0]


def _feature_load_label(total_features: int) -> str:
    if total_features >= 90:
        return "very_high"
    if total_features >= 70:
        return "high"
    if total_features >= 50:
        return "medium"
    return "lean"


def _variant_preference_label(best_simple: dict[str, Any] | None, best_rich: dict[str, Any] | None) -> str:
    if not best_simple or not best_rich:
        return "not_compared"
    simple_metrics = best_simple.get("metrics") or {}
    rich_metrics = best_rich.get("metrics") or {}
    simple_r2 = simple_metrics.get("r2")
    rich_r2 = rich_metrics.get("r2")
    simple_mape = simple_metrics.get("mape")
    rich_mape = rich_metrics.get("mape")
    if (
        isinstance(rich_r2, (int, float))
        and isinstance(simple_r2, (int, float))
        and isinstance(rich_mape, (int, float))
        and isinstance(simple_mape, (int, float))
    ):
        if rich_r2 > simple_r2 + 0.01 and rich_mape <= simple_mape + 0.3:
            return "rich_helped"
        if rich_mape < simple_mape - 0.5 and rich_r2 >= simple_r2 - 0.01:
            return "rich_helped"
        if simple_r2 > rich_r2 + 0.01 and simple_mape <= rich_mape + 0.3:
            return "simple_helped"
        if simple_mape < rich_mape - 0.5 and simple_r2 >= rich_r2 - 0.01:
            return "simple_helped"
    return "mixed"


def _target_preference_label(best_log_ppm2: dict[str, Any] | None, best_log_price: dict[str, Any] | None) -> str:
    if not best_log_ppm2 or not best_log_price:
        return "not_compared"
    ppm2_metrics = best_log_ppm2.get("metrics") or {}
    price_metrics = best_log_price.get("metrics") or {}
    ppm2_r2 = ppm2_metrics.get("r2")
    price_r2 = price_metrics.get("r2")
    ppm2_mape = ppm2_metrics.get("mape")
    price_mape = price_metrics.get("mape")
    if (
        isinstance(ppm2_r2, (int, float))
        and isinstance(price_r2, (int, float))
        and isinstance(ppm2_mape, (int, float))
        and isinstance(price_mape, (int, float))
    ):
        if price_r2 > ppm2_r2 + 0.01 and price_mape <= ppm2_mape + 0.3:
            return "log_price_helped"
        if price_mape < ppm2_mape - 0.5 and price_r2 >= ppm2_r2 - 0.01:
            return "log_price_helped"
        if ppm2_r2 > price_r2 + 0.01 and ppm2_mape <= price_mape + 0.3:
            return "log_ppm2_helped"
        if ppm2_mape < price_mape - 0.5 and ppm2_r2 >= price_r2 - 0.01:
            return "log_ppm2_helped"
    return "mixed"


def _per_type_feature_audit(model_info: dict[str, Any], top_n: int = 10) -> list[dict[str, Any]]:
    per_type_features = model_info.get("per_type_features") or {}
    per_type_metrics = model_info.get("per_type_metrics") or {}
    rows: list[dict[str, Any]] = []
    for property_type, info in per_type_features.items():
        if not isinstance(info, dict):
            continue
        candidates = list(info.get("candidate_matrix") or [])
        best_simple = _best_candidate(
            [candidate for candidate in candidates if candidate.get("feature_variant") == "simple"]
        )
        best_rich = _best_candidate(
            [candidate for candidate in candidates if candidate.get("feature_variant") == "rich"]
        )
        best_log_ppm2 = _best_candidate(
            [candidate for candidate in candidates if candidate.get("target_transform") == "log_ppm2"]
        )
        best_log_price = _best_candidate(
            [candidate for candidate in candidates if candidate.get("target_transform") == "log_price"]
        )
        selected_numeric = int(info.get("numeric_feature_count") or len(info.get("numeric_features") or []))
        selected_categorical = int(info.get("categorical_feature_count") or len(info.get("categorical_features") or []))
        total_features = int(info.get("total_feature_count") or (selected_numeric + selected_categorical))
        metrics = (
            (per_type_metrics.get(property_type) or {}) if isinstance(per_type_metrics.get(property_type), dict) else {}
        )
        top_features = (info.get("top_features") or [])[:5]
        hyperparameters = dict(info.get("model_hyperparameters") or {})
        rows.append(
            {
                "property_type": property_type,
                "r2": round(float(metrics.get("r2")), 6) if isinstance(metrics.get("r2"), (int, float)) else None,
                "mape": round(float(metrics.get("mape")), 6) if isinstance(metrics.get("mape"), (int, float)) else None,
                "selected_numeric": selected_numeric,
                "selected_categorical": selected_categorical,
                "selected_total": total_features,
                "feature_load": _feature_load_label(total_features),
                "chosen_feature_variant": info.get("feature_variant"),
                "chosen_target_transform": info.get("target_transform"),
                "training_policy": info.get("training_policy"),
                "routing_mode": info.get("routing_mode"),
                "blend_weight": info.get("blend_weight"),
                "feature_variant_signal": _variant_preference_label(best_simple, best_rich),
                "target_signal": _target_preference_label(best_log_ppm2, best_log_price),
                "top_features": top_features,
                "hyperparameters": {
                    key: hyperparameters.get(key)
                    for key in ("iterations", "learning_rate", "depth", "l2_leaf_reg", "min_data_in_leaf", "od_wait")
                    if key in hyperparameters
                },
            }
        )
    rows.sort(
        key=lambda item: (
            -(float(item["mape"]) if isinstance(item.get("mape"), (int, float)) else -1.0),
            float(item["r2"]) if isinstance(item.get("r2"), (int, float)) else 999.0,
            str(item.get("property_type") or ""),
        )
    )
    return rows[:top_n]


def _sorted_runs_with_deltas(
    leaderboard: list[dict[str, Any]],
    best_summary: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    best_metrics = ((best_summary or {}).get("train") or {}).get("combined_metrics") or {}
    rows: list[dict[str, Any]] = []
    for run in leaderboard:
        if not isinstance(run, dict):
            continue
        summary = _load_summary(run.get("summary_path"))
        train = (summary or {}).get("train") or {}
        combined = train.get("combined_metrics") or {}
        delta = _metric_delta(combined, best_metrics)
        rows.append(
            {
                "label": run.get("label"),
                "summary_path": run.get("summary_path"),
                "is_best": bool(run.get("is_best")),
                "failed": bool(run.get("failed")),
                "elapsed_sec": run.get("elapsed_sec"),
                "combined_metrics": combined,
                "delta_vs_best": delta,
                "verdict_vs_best": _delta_label(delta) if delta else ("best" if run.get("is_best") else "inconclusive"),
            }
        )
    rows.sort(
        key=lambda item: (
            -float((item.get("combined_metrics") or {}).get("r2") or -999.0),
            float((item.get("combined_metrics") or {}).get("mape") or 999999.0),
            str(item.get("label") or ""),
        )
    )
    return rows


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_reports(output_root: Path, leaderboard: list[dict[str, Any]], state: dict[str, Any]) -> None:
    best_summary = _load_summary(state.get("best_summary_path"))
    if best_summary is None:
        return

    best_train = best_summary.get("train") or {}
    best_model_path = best_train.get("model_path")
    best_model_info = get_model_info(best_model_path) if best_model_path else None
    if best_model_info is None:
        return

    sorted_runs = _sorted_runs_with_deltas(leaderboard, best_summary)
    report_payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "task_type": _get_catboost_task_type(),
        "best_run": {
            "label": best_summary.get("label"),
            "summary_path": state.get("best_summary_path"),
            "model_path": best_train.get("model_path"),
            "combined_metrics": best_train.get("combined_metrics"),
            "global_metrics": best_train.get("global_metrics"),
        },
        "run_leaderboard": sorted_runs,
        "variant_impact": _variant_impact(best_model_info),
        "high_signal_features": _top_feature_rollup(best_model_info),
        "low_signal_global_features": _low_signal_global_features(best_model_info),
        "dragging_segments": _dragging_segments(best_model_info),
        "per_type_feature_audit": _per_type_feature_audit(best_model_info),
    }
    _write_json(output_root / "impact_report.json", report_payload)

    best_combined = best_train.get("combined_metrics") or {}
    lines = [
        "# Research Queue Impact Report",
        "",
        f"Generated: {report_payload['generated_at']}",
        f"Best run: {best_summary.get('label')}",
        f"Best combined R2: {_fmt_metric(best_combined.get('r2'))}",
        f"Best combined MAPE: {_fmt_metric(best_combined.get('mape'), 2)}",
        "",
        "## Run Leaderboard",
        "",
        "| Run | R2 | MAPE | dR2 vs best | dMAPE vs best | Verdict |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for run in sorted_runs:
        combined = run.get("combined_metrics") or {}
        delta = run.get("delta_vs_best") or {}
        verdict = "best" if run.get("is_best") else run.get("verdict_vs_best")
        lines.append(
            f"| {run.get('label')} | {_fmt_metric(combined.get('r2'))} | {_fmt_metric(combined.get('mape'), 2)} | "
            f"{_fmt_metric(delta.get('r2'))} | {_fmt_metric(delta.get('mape'), 2)} | {verdict} |"
        )

    lines.extend(
        [
            "",
            "## Source Impact",
            "",
        ]
    )
    for label, payload in report_payload["variant_impact"].items():
        delta = payload.get("delta") or {}
        lines.append(
            f"- `{label}`: verdict `{payload.get('verdict')}`, dR2 `{_fmt_metric(delta.get('r2'))}`, "
            f"dMAPE `{_fmt_metric(delta.get('mape'), 2)}`"
        )

    lines.extend(
        [
            "",
            "## Highest-Signal Features",
            "",
        ]
    )
    for item in report_payload["high_signal_features"][:10]:
        lines.append(
            f"- `{item['feature']}`: seen in {item['occurrences']} type(s), avg score `{_fmt_metric(item['avg_score'], 3)}`"
        )

    lines.extend(
        [
            "",
            "## Lowest-Signal Global Features",
            "",
        ]
    )
    for item in report_payload["low_signal_global_features"][:10]:
        lines.append(f"- `{item['feature']}`: importance `{_fmt_metric(item['importance'], 6)}`")

    lines.extend(
        [
            "",
            "## Dragging Segments",
            "",
        ]
    )
    for item in report_payload["dragging_segments"]:
        lines.append(
            f"- `{item['property_type']}`: R2 `{_fmt_metric(item['r2'])}`, MAPE `{_fmt_metric(item['mape'], 2)}`, "
            f"test rows `{item.get('n_test', 'n/a')}`"
        )

    lines.extend(
        [
            "",
            "## Per-Type Feature Audit",
            "",
        ]
    )
    for item in report_payload["per_type_feature_audit"]:
        top_features = ", ".join(
            f"{feature.get('feature')} ({_fmt_metric(feature.get('score'), 3)})"
            for feature in item.get("top_features", [])
        )
        hp = item.get("hyperparameters") or {}
        hp_summary = ", ".join(f"{key}={hp[key]}" for key in hp) if hp else "n/a"
        lines.append(
            f"- `{item['property_type']}`: `{item['selected_numeric']} num + {item['selected_categorical']} cat = {item['selected_total']}` "
            f"({item['feature_load']}), current `{item['chosen_feature_variant']}` / `{item['chosen_target_transform']}` / "
            f"`{item['training_policy']}`, feature-search verdict `{item['feature_variant_signal']}`, target verdict "
            f"`{item['target_signal']}`, hp `{hp_summary}`, top `{top_features}`"
        )

    _write_text(output_root / "impact_report.md", "\n".join(lines) + "\n")


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
            "enable_dtm": True,
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

    leaderboard = _load_leaderboard(leaderboard_path)
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
            _write_reports(output_root, leaderboard, state)
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
        _write_reports(output_root, leaderboard, state)

    state.update(
        {
            "status": "finished" if time.time() < deadline else "timebox_reached",
            "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "leaderboard_path": str(leaderboard_path),
            "task_type": _get_catboost_task_type(),
        }
    )
    _write_json(state_path, state)
    _write_reports(output_root, leaderboard, state)
    print(json.dumps(state, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
