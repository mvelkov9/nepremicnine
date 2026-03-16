"""Statistics routes: overview, regions, distribution, trend."""

import logging
import os

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, Query, Request

from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services.regions_service import lookup_region
from app.utils.cache import cache_get, cache_set

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stats", tags=["stats"])

TRAIN_CSV = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "raw",
    "train.csv",
)


def _d96tm_to_wgs84(n: np.ndarray, e: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Convert D96/TM (ETRS89/TM) coordinates to WGS84 (lat, lon). Vectorized."""
    # GRS80 ellipsoid
    a = 6378137.0
    f = 1 / 298.257222101
    e2 = 2 * f - f * f
    e_prime2 = e2 / (1 - e2)

    # TM parameters for D96/TM
    k0 = 0.9999
    lon0 = np.radians(15.0)
    FE = 500000.0
    FN = -5000000.0

    x = e - FE
    y = n - FN
    M = y / k0

    mu = M / (a * (1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256))
    e1 = (1 - np.sqrt(1 - e2)) / (1 + np.sqrt(1 - e2))

    phi1 = (
        mu
        + (3 * e1 / 2 - 27 * e1**3 / 32) * np.sin(2 * mu)
        + (21 * e1**2 / 16 - 55 * e1**4 / 32) * np.sin(4 * mu)
        + (151 * e1**3 / 96) * np.sin(6 * mu)
        + (1097 * e1**4 / 512) * np.sin(8 * mu)
    )

    sin_phi1 = np.sin(phi1)
    cos_phi1 = np.cos(phi1)
    tan_phi1 = np.tan(phi1)

    N1 = a / np.sqrt(1 - e2 * sin_phi1**2)
    T1 = tan_phi1**2
    C1 = e_prime2 * cos_phi1**2
    R1 = a * (1 - e2) / (1 - e2 * sin_phi1**2) ** 1.5
    D = x / (N1 * k0)

    lat = phi1 - (N1 * tan_phi1 / R1) * (
        D**2 / 2
        - (5 + 3 * T1 + 10 * C1 - 4 * C1**2 - 9 * e_prime2) * D**4 / 24
        + (61 + 90 * T1 + 298 * C1 + 45 * T1**2 - 252 * e_prime2 - 3 * C1**2) * D**6 / 720
    )

    lon = lon0 + (1 / cos_phi1) * (
        D - (1 + 2 * T1 + C1) * D**3 / 6 + (5 - 2 * C1 + 28 * T1 - 3 * C1**2 + 8 * e_prime2 + 24 * T1**2) * D**5 / 120
    )

    return np.degrees(lat), np.degrees(lon)


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
    cached = await cache_get(request, cache_key)
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
        "min_price": round(float(df["price_eur"].min()), 2) if "price_eur" in df.columns else None,
        "max_price": round(float(df["price_eur"].max()), 2) if "price_eur" in df.columns else None,
        "std_price": round(float(df["price_eur"].std()), 2) if "price_eur" in df.columns else None,
        "avg_area": round(float(df["size_m2"].mean()), 2) if "size_m2" in df.columns else None,
        "median_area": round(float(df["size_m2"].median()), 2) if "size_m2" in df.columns else None,
        "avg_price_per_m2": None,
        "regions_count": int(df["statistical_region"].nunique()) if "statistical_region" in df.columns else None,
        "top_municipalities": [],
        "property_types": [],
    }

    # Year built stats
    if "year_built" in df.columns:
        yb = pd.to_numeric(df["year_built"], errors="coerce").dropna()
        if not yb.empty:
            result["year_built_avg"] = round(float(yb.mean()), 1)
            result["year_built_min"] = int(yb.min())
            result["year_built_max"] = int(yb.max())

    # Data years from source_label
    if "source_label" in df.columns:
        years = df["source_label"].astype(str).str[:4].unique().tolist()
        result["data_years"] = sorted(years)

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

    await cache_set(request, cache_key, result)
    return result


@router.get("/regions")
async def regions_stats(
    request: Request,
    _user: User = Depends(get_current_user),
):
    cache_key = "cache:stats:regions"
    cached = await cache_get(request, cache_key)
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
        entry["min_price"] = round(float(group["price_eur"].min()), 2) if "price_eur" in group.columns else None
        entry["max_price"] = round(float(group["price_eur"].max()), 2) if "price_eur" in group.columns else None
        results.append(entry)

    result = sorted(results, key=lambda x: x["count"], reverse=True)
    await cache_set(request, cache_key, result)
    return result


@router.get("/price-distribution")
async def price_distribution(
    request: Request,
    bins: int = Query(20, ge=5, le=100),
    property_type: str | None = None,
    _user: User = Depends(get_current_user),
):
    cache_key = f"cache:stats:price-distribution:{bins}:{property_type or 'all'}"
    cached = await cache_get(request, cache_key)
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
    await cache_set(request, cache_key, result)
    return result


@router.get("/trend")
async def trend(
    request: Request,
    _user: User = Depends(get_current_user),
):
    cache_key = "cache:stats:trend"
    cached = await cache_get(request, cache_key)
    if cached is not None:
        return cached

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

    await cache_set(request, cache_key, results)
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

    # Validate D96/TM coordinate range (latitude=northing, longitude=easting)
    # Easting: 350000-650000, Northing: 20000-210000
    df = df[
        (df["longitude"] > 350000) & (df["longitude"] < 650000) & (df["latitude"] > 20000) & (df["latitude"] < 210000)
    ]

    # Convert D96/TM (ETRS89/TM) → WGS84
    if len(df) > 0:
        wgs_lat, wgs_lon = _d96tm_to_wgs84(df["latitude"].values, df["longitude"].values)
        df = df.copy()
        df["latitude"] = wgs_lat
        df["longitude"] = wgs_lon

    # Sample if too many
    if len(df) > limit:
        df = df.sample(n=limit, random_state=42)

    area = _effective_area(df)

    # Build result DataFrame vectorized (no iterrows)
    result_df = pd.DataFrame(
        {
            "lat": df["latitude"].values,
            "lon": df["longitude"].values,
        }
    )

    result_df["price_eur"] = df["price_eur"].values if "price_eur" in df.columns else np.nan
    result_df["size_m2"] = df["size_m2"].values if "size_m2" in df.columns else np.nan
    result_df["municipality"] = df["municipality"].astype(str).values if "municipality" in df.columns else ""
    result_df["property_type"] = df["property_type"].astype(str).values if "property_type" in df.columns else ""
    result_df["rooms"] = df["rooms"].values if "rooms" in df.columns else np.nan

    # Year column — pick first available
    year_src = None
    for col in ["transaction_year", "source_label"]:
        if col in df.columns:
            year_src = col
            break
    result_df["year"] = df[year_src].astype(str).str[:4].values if year_src else ""

    # Price per m2
    area_arr = area.values
    valid_area = (area_arr > 0) & np.isfinite(area_arr)
    valid_price = result_df["price_eur"].notna().values & np.isfinite(result_df["price_eur"].values)
    price_per_m2 = np.where(
        valid_area & valid_price,
        np.round(result_df["price_eur"].values / np.where(area_arr > 0, area_arr, 1), 2),
        np.nan,
    )
    result_df["price_per_m2"] = price_per_m2

    # Replace NaN with None for valid JSON
    result_df = result_df.where(result_df.notna(), None)

    transactions = result_df.to_dict(orient="records")

    return {"transactions": transactions, "count": len(transactions)}
