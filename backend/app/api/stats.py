"""Statistics routes: overview, regions, distribution, trend."""

import json
import logging
import os

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, Query, Request

from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services.regions_service import lookup_region

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stats", tags=["stats"])

TRAIN_CSV = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "raw",
    "train.csv",
)

CACHE_TTL = 300  # 5 minutes


async def _cache_get(request: Request, key: str) -> dict | list | None:
    """Try to get cached value from Redis. Returns None on miss or error."""
    try:
        redis = getattr(request.app.state, "redis", None)
        if redis is None:
            return None
        raw = await redis.get(key)
        if raw is not None:
            return json.loads(raw)
    except Exception:
        logger.debug("Redis cache miss/error for key=%s", key)
    return None


async def _cache_set(request: Request, key: str, value) -> None:
    """Store value in Redis cache with TTL. Silently ignores errors."""
    try:
        redis = getattr(request.app.state, "redis", None)
        if redis is None:
            return
        await redis.set(key, json.dumps(value, default=str), ex=CACHE_TTL)
    except Exception:
        logger.debug("Redis cache set error for key=%s", key)


def _load_df(property_type: str | None = None) -> pd.DataFrame | None:
    if not os.path.exists(TRAIN_CSV):
        return None
    df = pd.read_csv(TRAIN_CSV)
    if property_type and "property_type" in df.columns:
        df = df[df["property_type"] == property_type]
    return df


def _effective_area(df: pd.DataFrame) -> pd.Series:
    """Return uporabna_povrsina when available (>0), otherwise size_m2."""
    area = df["size_m2"].copy()
    if "uporabna_povrsina" in df.columns:
        up = df["uporabna_povrsina"]
        mask = up.notna() & (up > 0)
        area.loc[mask] = up.loc[mask]
    return area


def _format_eur(val: float) -> str:
    """Human-readable EUR: 150k, 1.2M etc."""
    if val >= 1_000_000:
        return f"{val / 1_000_000:.1f}M"
    if val >= 1_000:
        return f"{val / 1_000:.0f}k"
    return f"{val:.0f}"


@router.get("/overview")
async def overview(
    request: Request,
    property_type: str | None = None,
    _user: User = Depends(get_current_user),
):
    cache_key = f"cache:stats:overview:{property_type or 'all'}"
    cached = await _cache_get(request, cache_key)
    if cached is not None:
        return cached

    df = _load_df(property_type)
    if df is None or df.empty:
        return {
            "total_records": 0,
            "avg_price": None,
            "median_price": None,
            "avg_area": None,
            "median_area": None,
            "avg_price_per_m2": None,
            "top_municipalities": [],
            "property_types": [],
        }

    result = {
        "total_records": len(df),
        "avg_price": round(float(df["price_eur"].mean()), 2) if "price_eur" in df.columns else None,
        "median_price": round(float(df["price_eur"].median()), 2) if "price_eur" in df.columns else None,
        "avg_area": round(float(df["size_m2"].mean()), 2) if "size_m2" in df.columns else None,
        "median_area": round(float(df["size_m2"].median()), 2) if "size_m2" in df.columns else None,
        "avg_price_per_m2": None,
        "top_municipalities": [],
        "property_types": [],
    }

    if "price_eur" in df.columns and "size_m2" in df.columns:
        tmp = df[["price_eur"]].copy()
        tmp["_area"] = _effective_area(df)
        valid = tmp.dropna()
        valid = valid[valid["_area"] > 0]
        if not valid.empty:
            result["avg_price_per_m2"] = round(float((valid["price_eur"] / valid["_area"]).mean()), 2)

    if "municipality" in df.columns:
        muni_groups = df.groupby("municipality")
        muni_stats = []
        for name, group in muni_groups:
            entry = {"name": name, "count": len(group)}
            if "price_eur" in group.columns:
                entry["avg_price"] = round(float(group["price_eur"].mean()), 2)
            muni_stats.append(entry)
        muni_stats.sort(key=lambda x: x["count"], reverse=True)
        result["top_municipalities"] = muni_stats

    if "property_type" in df.columns:
        types = df["property_type"].value_counts()
        result["property_types"] = [{"type": t, "count": int(c)} for t, c in types.items()]

    await _cache_set(request, cache_key, result)
    return result


@router.get("/regions")
async def regions_stats(
    request: Request,
    _user: User = Depends(get_current_user),
):
    cache_key = "cache:stats:regions"
    cached = await _cache_get(request, cache_key)
    if cached is not None:
        return cached

    df = _load_df()
    if df is None or df.empty:
        return []

    # Ensure statistical_region column
    if "statistical_region" not in df.columns and "municipality" in df.columns:
        df["statistical_region"] = df["municipality"].apply(
            lambda m: lookup_region(str(m)) if pd.notna(m) else "neznana"
        )

    if "statistical_region" not in df.columns:
        return []

    results = []
    for region, group in df.groupby("statistical_region"):
        entry = {
            "region": region,
            "count": len(group),
            "avg_price": round(float(group["price_eur"].mean()), 2) if "price_eur" in group.columns else None,
            "median_price": round(float(group["price_eur"].median()), 2) if "price_eur" in group.columns else None,
            "avg_price_per_m2": None,
        }
        if "price_eur" in group.columns and "size_m2" in group.columns:
            tmp = group[["price_eur"]].copy()
            tmp["_area"] = _effective_area(group)
            valid = tmp.dropna()
            valid = valid[valid["_area"] > 0]
            if not valid.empty:
                entry["avg_price_per_m2"] = round(float((valid["price_eur"] / valid["_area"]).mean()), 2)
                entry["median_price_per_m2"] = round(float((valid["price_eur"] / valid["_area"]).median()), 2)
        results.append(entry)

    result = sorted(results, key=lambda x: x["count"], reverse=True)
    await _cache_set(request, cache_key, result)
    return result


@router.get("/price-distribution")
async def price_distribution(
    request: Request,
    bins: int = Query(20, ge=5, le=100),
    property_type: str | None = None,
    _user: User = Depends(get_current_user),
):
    cache_key = f"cache:stats:price-distribution:{bins}:{property_type or 'all'}"
    cached = await _cache_get(request, cache_key)
    if cached is not None:
        return cached

    df = _load_df(property_type)
    if df is None or "price_eur" not in df.columns or df.empty:
        return {"bins": [], "counts": [], "bin_labels": []}

    prices = df["price_eur"].dropna()
    prices = prices[(prices > 0) & (prices < prices.quantile(0.99))]
    if prices.empty:
        return {"bins": [], "counts": [], "bin_labels": []}

    counts_arr, bin_edges = np.histogram(prices, bins=bins)
    bin_labels = [f"{_format_eur(bin_edges[i])}\u2013{_format_eur(bin_edges[i + 1])}" for i in range(len(counts_arr))]

    result = {
        "bins": [float(b) for b in bin_edges],
        "counts": [int(c) for c in counts_arr],
        "bin_labels": bin_labels,
    }
    await _cache_set(request, cache_key, result)
    return result


@router.get("/trend")
async def trend(
    _user: User = Depends(get_current_user),
):
    df = _load_df()
    if df is None or df.empty:
        return []

    # Detect year column
    year_col = None
    for col in ["source_label", "year", "sale_year"]:
        if col in df.columns:
            year_col = col
            break

    if year_col is None:
        return []

    df["_year"] = df[year_col].astype(str).str[:4]
    results = []

    for year, group in sorted(df.groupby("_year")):
        entry = {
            "year": str(year),
            "count": len(group),
            "avg_price": round(float(group["price_eur"].mean()), 2) if "price_eur" in group.columns else None,
            "median_price": round(float(group["price_eur"].median()), 2) if "price_eur" in group.columns else None,
            "avg_price_per_m2": None,
            "by_type": {},
        }
        if "size_m2" in group.columns and "price_eur" in group.columns:
            tmp = group[["price_eur"]].copy()
            tmp["_area"] = _effective_area(group)
            valid = tmp.dropna()
            valid = valid[valid["_area"] > 0]
            if not valid.empty:
                entry["avg_price_per_m2"] = round(float((valid["price_eur"] / valid["_area"]).mean()), 2)
        if "property_type" in group.columns:
            for pt, pt_group in group.groupby("property_type"):
                if len(pt_group) < 5:
                    continue
                pt_entry: dict = {
                    "count": len(pt_group),
                    "avg_price": round(float(pt_group["price_eur"].mean()), 2)
                    if "price_eur" in pt_group.columns
                    else None,
                    "median_price": round(float(pt_group["price_eur"].median()), 2)
                    if "price_eur" in pt_group.columns
                    else None,
                }
                if "size_m2" in pt_group.columns and "price_eur" in pt_group.columns:
                    pt_tmp = pt_group[["price_eur"]].copy()
                    pt_tmp["_area"] = _effective_area(pt_group)
                    pt_valid = pt_tmp.dropna()
                    pt_valid = pt_valid[pt_valid["_area"] > 0]
                    if not pt_valid.empty:
                        pt_entry["median_price_per_m2"] = round(
                            float((pt_valid["price_eur"] / pt_valid["_area"]).median()), 2
                        )
                entry["by_type"][pt] = pt_entry
        results.append(entry)

    return results


@router.get("/municipalities-by-region")
async def municipalities_by_region(
    _user: User = Depends(get_current_user),
):
    """Return {region: [municipality, ...]} from training data."""
    df = _load_df()
    if df is None or "municipality" not in df.columns:
        return {}

    if "statistical_region" not in df.columns:
        df["statistical_region"] = df["municipality"].apply(
            lambda m: lookup_region(str(m)) if pd.notna(m) else "neznana"
        )

    mapping = df[["municipality", "statistical_region"]].dropna().drop_duplicates()
    result: dict[str, list[str]] = {}
    for region, group in mapping.groupby("statistical_region"):
        result[str(region)] = sorted(group["municipality"].unique().tolist())
    return result


@router.get("/map-transactions")
async def map_transactions(
    property_type: str | None = None,
    statistical_region: str | None = None,
    year: str | None = None,
    municipality: str | None = None,
    limit: int = Query(5000, ge=100, le=50000),
    _user: User = Depends(get_current_user),
):
    """Return transaction points for map visualization (WGS84 coords)."""
    df = _load_df()
    if df is None or df.empty:
        return {"transactions": [], "count": 0}

    # Ensure statistical_region
    if "statistical_region" not in df.columns and "municipality" in df.columns:
        df["statistical_region"] = df["municipality"].apply(
            lambda m: lookup_region(str(m)) if pd.notna(m) else "neznana"
        )

    # Apply filters
    if property_type and "property_type" in df.columns:
        df = df[df["property_type"] == property_type]
    if statistical_region and "statistical_region" in df.columns:
        df = df[df["statistical_region"] == statistical_region]
    if municipality and "municipality" in df.columns:
        df = df[df["municipality"] == municipality]

    # Year filter
    if year:
        year_col = None
        for col in ["source_label", "year", "sale_year", "transaction_year"]:
            if col in df.columns:
                year_col = col
                break
        if year_col:
            df = df[df[year_col].astype(str).str[:4] == year]

    # Require lat/lon
    if "latitude" not in df.columns or "longitude" not in df.columns:
        return {"transactions": [], "count": 0}

    df = df.dropna(subset=["latitude", "longitude"])
    df = df[(df["latitude"] > 0) & (df["longitude"] > 0)]

    # Sample if too many
    if len(df) > limit:
        df = df.sample(n=limit, random_state=42)

    area = _effective_area(df)

    transactions = []
    for _, row in df.iterrows():
        price = row.get("price_eur")
        size = float(area.loc[row.name]) if row.name in area.index else None
        price_per_m2 = float(price / size) if price and size and size > 0 else None

        transactions.append(
            {
                "lat": float(row["latitude"]),
                "lon": float(row["longitude"]),
                "price_eur": float(price) if pd.notna(price) else None,
                "size_m2": float(row.get("size_m2", 0)) if pd.notna(row.get("size_m2")) else None,
                "price_per_m2": round(price_per_m2, 2) if price_per_m2 else None,
                "municipality": str(row.get("municipality", "")),
                "property_type": str(row.get("property_type", "")),
                "year": str(row.get("transaction_year", row.get("source_label", "")))[:4],
                "rooms": float(row.get("rooms", 0)) if pd.notna(row.get("rooms")) else None,
            }
        )

    return {"transactions": transactions, "count": len(transactions)}
