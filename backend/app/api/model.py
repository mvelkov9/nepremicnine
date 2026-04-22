"""Model info routes — current model metadata, feature importance, diagnostics, runs."""

from __future__ import annotations

import json
import logging
import math
import os

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user, require_admin
from app.models.model_run import ModelRun
from app.models.user import User
from app.schemas.model import BenchmarkProofResponse, BenchmarkSummaryResponse, ModelInfoResponse
from app.services.model_service import build_gurs_benchmark_payload, get_model_info
from app.utils.cache import cache_get, cache_set, invalidate_request_caches
from app.utils.slovenian_labels import labels_match

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/model", tags=["model"])
DATA_DIR = os.path.realpath(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"))
RESEARCH_QUEUE_DIR = os.path.join(DATA_DIR, "models", "research_queue")


def _relative_data_path(path: str | None) -> str | None:
    if not path:
        return None
    resolved = os.path.realpath(path)
    if resolved.startswith(DATA_DIR + os.sep) or resolved == DATA_DIR:
        return os.path.relpath(resolved, DATA_DIR).replace("\\", "/")
    return path


def _load_research_impact_report() -> dict | None:
    report_path = os.path.join(RESEARCH_QUEUE_DIR, "impact_report.json")
    if not os.path.exists(report_path):
        return None
    try:
        with open(report_path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        logger.warning("Failed to read research impact report from %s", report_path)
        return None


async def _load_cached_gurs_benchmark_payload(request: Request) -> dict:
    # Benchmark rebuild reads the full CSV + runs predictions (~30-60s).
    # Results only change when the model is retrained, so cache aggressively (24h).
    # Cache is invalidated automatically on model retrain via invalidate_cache_prefixes.
    cache_key = "cache:model:benchmark:gurs:all"
    cached = await cache_get(request, cache_key)
    if cached is not None:
        return cached

    payload = build_gurs_benchmark_payload()
    await cache_set(request, cache_key, payload, ttl=86400)
    return payload


@router.get("/info", response_model=ModelInfoResponse)
async def model_info(request: Request, response: Response, _user: User = Depends(require_admin)):
    """Get current trained model metadata."""
    response.headers["Cache-Control"] = "private, max-age=60"

    cache_key = "cache:model:info"
    cached = await cache_get(request, cache_key)
    if cached is not None:
        return ModelInfoResponse(**cached)

    info = get_model_info()
    if info is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No trained model found")
    result = ModelInfoResponse(**{**info, "source_csv_path": _relative_data_path(info.get("csv_path"))})
    await cache_set(request, cache_key, result.model_dump())
    return result


@router.get("/importance")
async def feature_importance(request: Request, response: Response, _user: User = Depends(get_current_user)):
    """Get feature importance from the global model."""
    response.headers["Cache-Control"] = "private, max-age=60"

    cache_key = "cache:model:importance"
    cached = await cache_get(request, cache_key)
    if cached is not None:
        return cached

    info = get_model_info()
    if info is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No trained model found")

    importance = info.get("global_importance", {})
    labels = info.get("feature_labels", {})

    items = sorted(importance.items(), key=lambda x: x[1], reverse=True)
    result = [
        {
            "feature": feat,
            "label": labels.get(feat.split("__")[-1], feat),
            "importance": round(val, 4),
        }
        for feat, val in items
    ]
    await cache_set(request, cache_key, result)
    return result


@router.get("/diagnostics")
async def model_diagnostics(request: Request, response: Response, _user: User = Depends(require_admin)):
    """Get per-type and per-region model diagnostics."""
    response.headers["Cache-Control"] = "private, max-age=60"

    cache_key = "cache:model:diagnostics"
    cached = await cache_get(request, cache_key)
    if cached is not None:
        return cached

    info = get_model_info()
    if info is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No trained model found")

    result = {
        "version": info.get("version"),
        "trained_at": info.get("trained_at"),
        "rows": info.get("rows"),
        "train_rows": info.get("train_rows"),
        "test_rows": info.get("test_rows"),
        "model_type": info.get("model_type", "HistGradientBoostingRegressor"),
        "used_features": info.get("used_features", []),
        "global_metrics": info.get("global_metrics"),
        "combined_metrics": info.get("combined_metrics"),
        "ev_baseline_metrics": info.get("ev_baseline_metrics"),
        "variant_matrix": info.get("variant_matrix"),
        "variant_benchmarks": info.get("variant_benchmarks"),
        "per_type_metrics": info.get("per_type_metrics", {}),
        "per_type_features": info.get("per_type_features", {}),
        "per_region_metrics": info.get("per_region_metrics", {}),
        "per_type_count": info.get("per_type_count", 0),
        "type_models_trained": info.get("type_models_trained", []),
        "data_preparation": info.get("data_preparation"),
        "segment_diagnostics": info.get("segment_diagnostics"),
        "research_impact": _load_research_impact_report(),
    }
    await cache_set(request, cache_key, result)
    return result


@router.get("/runs")
async def model_runs(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    """Get model training run history."""
    offset = (page - 1) * per_page
    stmt = (
        select(ModelRun, func.count(ModelRun.id).over().label("total_count"))
        .order_by(ModelRun.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    rows = (await db.execute(stmt)).all()
    total = rows[0].total_count if rows else 0
    pages = math.ceil(total / per_page) if total > 0 else 0

    items = [
        {
            "id": row.ModelRun.id,
            "source_csv_path": _relative_data_path(row.ModelRun.source_csv_path),
            "rows": row.ModelRun.rows,
            "mae": row.ModelRun.mae,
            "rmse": row.ModelRun.rmse,
            "r2": row.ModelRun.r2,
            "mape": row.ModelRun.mape,
            "median_ae": row.ModelRun.median_ae,
            "duration_sec": row.ModelRun.duration_sec,
            "per_type_count": row.ModelRun.per_type_count,
            "model_type": row.ModelRun.model_type,
            "features": json.loads(row.ModelRun.features_json) if row.ModelRun.features_json else None,
            "importance": json.loads(row.ModelRun.importance_json) if row.ModelRun.importance_json else None,
            "combined_metrics": json.loads(row.ModelRun.combined_metrics_json)
            if row.ModelRun.combined_metrics_json
            else None,
            "created_at": row.ModelRun.created_at.isoformat(),
        }
        for row in rows
    ]
    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
    }


@router.get("/benchmark/gurs-summary", response_model=BenchmarkSummaryResponse)
async def gurs_benchmark_summary(
    request: Request,
    response: Response,
    _user: User = Depends(require_admin),
):
    """Return summary proof that compares the current model against GURS on shared coverage."""
    response.headers["Cache-Control"] = "private, max-age=300"

    info = get_model_info()
    if info is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No trained model found")

    payload = await _load_cached_gurs_benchmark_payload(request)
    return BenchmarkSummaryResponse(**payload.get("summary", {}))


@router.get("/benchmark/gurs-transactions", response_model=BenchmarkProofResponse)
async def gurs_benchmark_transactions(
    request: Request,
    response: Response,
    region: str | None = None,
    municipality: str | None = None,
    property_type: str | None = None,
    year: int | None = Query(None, ge=1800, le=2100),
    winner: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    sort: str = Query("improvement_eur"),
    order: str = Query("desc"),
    _user: User = Depends(require_admin),
):
    """Return transaction-level proof rows comparing model predictions against GURS."""
    response.headers["Cache-Control"] = "private, max-age=300"

    info = get_model_info()
    if info is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No trained model found")

    payload = await _load_cached_gurs_benchmark_payload(request)
    rows = list(payload.get("rows", []))

    if region:
        rows = [row for row in rows if labels_match(row.get("region"), region)]
    if municipality:
        rows = [row for row in rows if labels_match(row.get("municipality"), municipality)]
    if property_type:
        property_key = str(property_type).casefold()
        rows = [row for row in rows if str(row.get("property_type") or "").casefold() == property_key]
    if year is not None:
        rows = [row for row in rows if row.get("transaction_year") == year]
    if winner:
        winner_key = str(winner).casefold()
        rows = [row for row in rows if str(row.get("winner") or "").casefold() == winner_key]
    if search:
        search_key = str(search).strip().casefold()
        rows = [
            row
            for row in rows
            if search_key
            in " ".join(
                [
                    str(row.get("municipality") or ""),
                    str(row.get("region") or ""),
                    str(row.get("property_type") or ""),
                    str(row.get("transaction_year") or ""),
                ]
            ).casefold()
        ]

    sort_field_map = {
        "municipality": "municipality",
        "region": "region",
        "property_type": "property_type",
        "transaction_year": "transaction_year",
        "price_eur": "price_eur",
        "model_price_eur": "model_price_eur",
        "gurs_price_eur": "gurs_price_eur",
        "model_abs_error": "model_abs_error",
        "gurs_abs_error": "gurs_abs_error",
        "improvement_eur": "improvement_eur",
        "improvement_pct": "improvement_pct",
        "winner": "winner",
    }
    sort_field = sort_field_map.get(sort, "improvement_eur")
    reverse = str(order).casefold() != "asc"
    rows = sorted(
        rows,
        key=lambda row: (
            row.get(sort_field) is None,
            str(row.get(sort_field) or "").casefold()
            if sort_field in {"municipality", "region", "property_type", "winner"}
            else float(row.get(sort_field) or 0),
        ),
        reverse=reverse,
    )

    total = len(rows)
    pages = math.ceil(total / page_size) if total > 0 else 0
    offset = (page - 1) * page_size
    items = rows[offset : offset + page_size]

    return BenchmarkProofResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
        filters={
            "region": region,
            "municipality": municipality,
            "property_type": property_type,
            "year": year,
            "winner": winner,
            "search": search,
        },
        sort=sort_field,
        order="desc" if reverse else "asc",
    )


@router.delete("/runs/clear", status_code=status.HTTP_200_OK)
async def clear_model_runs(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    """Delete all model run records."""
    result = await db.execute(select(func.count(ModelRun.id)))
    count = result.scalar() or 0
    await db.execute(delete(ModelRun))
    await db.commit()
    await invalidate_request_caches(request, prefixes=("cache:activity:", "cache:admin:", "cache:model:"))
    return {"deleted": count}
