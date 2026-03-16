"""Statistics routes: overview, regions, distribution, trend."""

import logging
import os
from collections.abc import Iterable

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services.regions_service import lookup_region
from app.utils.cache import cache_get, cache_set
from app.utils.municipality import municipality_slug, normalize_municipality_name
from app.utils.slovenian_labels import format_municipality_label, format_region_label, labels_match

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
        normalized = str(property_type).strip().casefold()
        df = df[df["property_type"].astype(str).str.casefold() == normalized]
    return df


def _effective_area(df: pd.DataFrame) -> pd.Series:
    """Return uporabna_povrsina when available (>0), otherwise size_m2."""
    area = df["size_m2"].copy() if "size_m2" in df.columns else pd.Series(np.nan, index=df.index, dtype=float)
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


def _round_or_none(value: float | int | None, digits: int = 2):
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def _detect_year_column(df: pd.DataFrame) -> str | None:
    for col in [
        "transaction_year",
        "source_label",
        "sale_year",
        "year",
        "sale_date",
        "transaction_date",
    ]:
        if col in df.columns:
            return col
    return None


def _ensure_regions(df: pd.DataFrame) -> pd.DataFrame:
    if "statistical_region" in df.columns or "municipality" not in df.columns:
        return df

    frame = df.copy()
    frame["statistical_region"] = frame["municipality"].apply(
        lambda municipality: lookup_region(str(municipality)) if pd.notna(municipality) else "neznana"
    )
    return frame


def _prepare_market_df(property_type: str | None = None) -> pd.DataFrame | None:
    df = _load_df(property_type)
    if df is None or df.empty:
        return None

    frame = _ensure_regions(df.copy())

    if "municipality" in frame.columns:
        frame["municipality"] = frame["municipality"].map(lambda value: format_municipality_label(value) or "unknown")
        frame["_municipality_slug"] = frame["municipality"].map(municipality_slug)
        frame["_municipality_normalized"] = frame["municipality"].map(normalize_municipality_name)

    if "statistical_region" in frame.columns:
        frame["statistical_region"] = frame["statistical_region"].map(lambda value: format_region_label(value) or "Neznana")

    frame["_area"] = _effective_area(frame)

    if "price_eur" in frame.columns:
        price = pd.to_numeric(frame["price_eur"], errors="coerce")
        valid_area = frame["_area"].notna() & (frame["_area"] > 0)
        frame["_price_per_m2"] = np.where(valid_area, np.round(price / frame["_area"], 2), np.nan)
    else:
        frame["_price_per_m2"] = np.nan

    year_col = _detect_year_column(frame)
    frame["_year"] = (
        frame[year_col].astype(str).str.extract(r"(\d{4})", expand=False)
        if year_col
        else pd.Series(pd.NA, index=frame.index)
    )

    date_col = next((col for col in ["transaction_date", "sale_date", "datum_sklenitve"] if col in frame.columns), None)
    if date_col:
        frame["_sale_date"] = pd.to_datetime(frame[date_col], errors="coerce")
    else:
        frame["_sale_date"] = pd.NaT

    return frame


def _prepare_map_coordinates(df: pd.DataFrame) -> tuple[pd.DataFrame, str | None]:
    """Return a map-ready frame with WGS84 coordinates from either WGS84 or D96/TM inputs."""
    if "latitude" not in df.columns or "longitude" not in df.columns:
        return df.iloc[0:0].copy(), "no_coordinates"

    lat = pd.to_numeric(df["latitude"], errors="coerce")
    lon = pd.to_numeric(df["longitude"], errors="coerce")

    wgs_mask = lat.between(45.0, 47.5) & lon.between(13.0, 17.5)
    d96_mask = lon.between(350000, 650000) & lat.between(20000, 210000)
    valid_mask = wgs_mask | d96_mask

    if not valid_mask.any():
        return df.iloc[0:0].copy(), "no_coordinates"

    frame = df.loc[valid_mask].copy()
    frame["_map_lat"] = np.nan
    frame["_map_lon"] = np.nan

    valid_lat = lat.loc[frame.index].to_numpy(dtype=float)
    valid_lon = lon.loc[frame.index].to_numpy(dtype=float)
    valid_wgs = wgs_mask.loc[frame.index].to_numpy(dtype=bool)
    valid_d96 = d96_mask.loc[frame.index].to_numpy(dtype=bool)

    frame.loc[frame.index[valid_wgs], "_map_lat"] = valid_lat[valid_wgs]
    frame.loc[frame.index[valid_wgs], "_map_lon"] = valid_lon[valid_wgs]

    if valid_d96.any():
        converted_lat, converted_lon = _d96tm_to_wgs84(valid_lat[valid_d96], valid_lon[valid_d96])
        frame.loc[frame.index[valid_d96], "_map_lat"] = converted_lat
        frame.loc[frame.index[valid_d96], "_map_lon"] = converted_lon

    frame = frame.dropna(subset=["_map_lat", "_map_lon"])
    if frame.empty:
        return frame, "no_coordinates"

    return frame, None


def _mode_or_none(values: pd.Series) -> str | None:
    if values.empty:
        return None
    mode = values.dropna().mode()
    return str(mode.iloc[0]) if not mode.empty else None


def _serialize_price_row(row: pd.Series) -> dict:
    return {
        "municipality": format_municipality_label(row.get("municipality")) or row.get("municipality"),
        "slug": row.get("_municipality_slug") or municipality_slug(row.get("municipality")),
        "region": format_region_label(row.get("statistical_region")) or row.get("statistical_region"),
        "property_type": row.get("property_type"),
        "price_eur": _round_or_none(row.get("price_eur")),
        "size_m2": _round_or_none(row.get("_area"), 1),
        "price_per_m2": _round_or_none(row.get("_price_per_m2")),
        "year": str(row.get("_year")) if pd.notna(row.get("_year")) else None,
        "year_built": int(row["year_built"]) if "year_built" in row.index and pd.notna(row["year_built"]) else None,
        "lat": _round_or_none(row.get("latitude"), 6),
        "lon": _round_or_none(row.get("longitude"), 6),
    }


def _summarize_yearly(grouped: Iterable[tuple[str, pd.DataFrame]]) -> list[dict]:
    output = []
    for year, group in grouped:
        output.append(
            {
                "year": str(year),
                "count": int(len(group)),
                "avg_price": _round_or_none(group["price_eur"].mean()) if "price_eur" in group.columns else None,
                "median_price": _round_or_none(group["price_eur"].median()) if "price_eur" in group.columns else None,
                "avg_price_per_m2": _round_or_none(group["_price_per_m2"].dropna().mean()),
                "median_price_per_m2": _round_or_none(group["_price_per_m2"].dropna().median()),
            }
        )
    return output


def _municipality_stats(group: pd.DataFrame) -> dict:
    return {
        "municipality": format_municipality_label(group["municipality"].iloc[0]) or str(group["municipality"].iloc[0]),
        "slug": str(group["_municipality_slug"].iloc[0])
        if "_municipality_slug" in group.columns
        else municipality_slug(group["municipality"].iloc[0]),
        "region": (
            format_region_label(_mode_or_none(group["statistical_region"])) if "statistical_region" in group.columns else None
        ),
        "count": int(len(group)),
        "avg_price": _round_or_none(group["price_eur"].mean()) if "price_eur" in group.columns else None,
        "median_price": _round_or_none(group["price_eur"].median()) if "price_eur" in group.columns else None,
        "avg_price_per_m2": _round_or_none(group["_price_per_m2"].dropna().mean()),
        "median_price_per_m2": _round_or_none(group["_price_per_m2"].dropna().median()),
        "latest_year": str(group["_year"].dropna().max())
        if "_year" in group.columns and group["_year"].notna().any()
        else None,
    }


def _find_municipality_frame(df: pd.DataFrame, slug_or_name: str) -> pd.DataFrame:
    slug = municipality_slug(slug_or_name)
    normalized = normalize_municipality_name(slug_or_name)

    by_slug = df[df["_municipality_slug"] == slug] if "_municipality_slug" in df.columns else pd.DataFrame()
    if not by_slug.empty:
        return by_slug

    if "_municipality_normalized" in df.columns:
        by_name = df[df["_municipality_normalized"] == normalized]
        if not by_name.empty:
            return by_name

    return pd.DataFrame(columns=df.columns)


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
    property_type: str | None = None,
    _user: User = Depends(get_current_user),
):
    cache_key = f"cache:stats:regions:{property_type or 'all'}"
    cached = await cache_get(request, cache_key)
    if cached is not None:
        return cached

    df = _prepare_market_df(property_type)
    if df is None or df.empty:
        return []

    if "statistical_region" not in df.columns:
        return []

    results = []
    for region, group in df.groupby("statistical_region"):
        entry = {
            "region": format_region_label(region) or region,
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
    property_type: str | None = None,
    _user: User = Depends(get_current_user),
):
    cache_key = f"cache:stats:trend:{property_type or 'all'}"
    cached = await cache_get(request, cache_key)
    if cached is not None:
        return cached

    df = _load_df(property_type)
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


@router.get("/market-home")
async def market_home(
    request: Request,
    property_type: str | None = None,
    _user: User = Depends(get_current_user),
):
    cache_key = f"cache:stats:market-home:{property_type or 'all'}"
    cached = await cache_get(request, cache_key)
    if cached is not None:
        return cached

    df = _prepare_market_df(property_type=property_type)
    if df is None or df.empty:
        return {
            "headline": {
                "total_records": 0,
                "municipalities_count": 0,
                "regions_count": 0,
                "avg_price": None,
                "median_price": None,
                "avg_price_per_m2": None,
                "latest_year": None,
            },
            "active_property_type": property_type,
            "largest_markets": [],
            "price_leaders": [],
            "region_snapshot": [],
            "latest_sales": [],
            "year_coverage": [],
            "property_type_mix": [],
        }

    municipality_groups = (
        [_municipality_stats(group) for _, group in df.groupby("_municipality_slug")]
        if "municipality" in df.columns
        else []
    )
    municipality_groups.sort(key=lambda item: item["count"], reverse=True)

    price_leaders = [
        item
        for item in sorted(
            municipality_groups,
            key=lambda item: (
                item["median_price_per_m2"] is not None,
                item["median_price_per_m2"] or 0,
                item["count"],
            ),
            reverse=True,
        )
        if item["median_price_per_m2"] is not None and item["count"] >= 2
    ][:8]

    region_snapshot = []
    if "statistical_region" in df.columns:
        for region, group in df.groupby("statistical_region"):
            price_per_m2 = group["_price_per_m2"].dropna()
            region_snapshot.append(
                {
                    "region": format_region_label(region) or str(region),
                    "count": int(len(group)),
                    "avg_price": _round_or_none(group["price_eur"].mean()) if "price_eur" in group.columns else None,
                    "median_price": _round_or_none(group["price_eur"].median())
                    if "price_eur" in group.columns
                    else None,
                    "median_price_per_m2": _round_or_none(price_per_m2.median()),
                }
            )
        region_snapshot.sort(key=lambda item: item["count"], reverse=True)

    latest_frame = df.dropna(subset=["price_eur"]).copy() if "price_eur" in df.columns else df.copy()
    if "_sale_date" in latest_frame.columns and latest_frame["_sale_date"].notna().any():
        latest_frame = latest_frame.sort_values(["_sale_date", "price_eur"], ascending=[False, False])
    elif "_year" in latest_frame.columns and latest_frame["_year"].notna().any():
        latest_frame = latest_frame.sort_values(["_year", "price_eur"], ascending=[False, False])
    else:
        latest_frame = latest_frame.sort_index(ascending=False)
    latest_sales = [_serialize_price_row(row) for _, row in latest_frame.head(10).iterrows()]

    year_coverage = []
    if "_year" in df.columns and df["_year"].notna().any():
        grouped = sorted(df[df["_year"].notna()].groupby("_year"), key=lambda item: int(item[0]))
        year_coverage = _summarize_yearly(grouped)

    property_type_mix = []
    if "property_type" in df.columns:
        counts = df["property_type"].fillna("unknown").value_counts()
        total = int(counts.sum()) or 1
        property_type_mix = [
            {
                "property_type": str(property_type),
                "count": int(count),
                "share": round(int(count) / total, 4),
            }
            for property_type, count in counts.items()
        ]

    result = {
        "headline": {
            "total_records": int(len(df)),
            "municipalities_count": int(df["municipality"].nunique()) if "municipality" in df.columns else 0,
            "regions_count": int(df["statistical_region"].nunique()) if "statistical_region" in df.columns else 0,
            "avg_price": _round_or_none(df["price_eur"].mean()) if "price_eur" in df.columns else None,
            "median_price": _round_or_none(df["price_eur"].median()) if "price_eur" in df.columns else None,
            "avg_price_per_m2": _round_or_none(df["_price_per_m2"].dropna().mean()),
            "latest_year": str(df["_year"].dropna().max())
            if "_year" in df.columns and df["_year"].notna().any()
            else None,
        },
        "active_property_type": property_type,
        "largest_markets": municipality_groups[:10],
        "price_leaders": price_leaders,
        "region_snapshot": region_snapshot[:8],
        "latest_sales": latest_sales,
        "year_coverage": year_coverage,
        "property_type_mix": property_type_mix,
    }
    await cache_set(request, cache_key, result)
    return result


@router.get("/municipality/{slug}")
async def municipality_detail(
    slug: str,
    request: Request,
    _user: User = Depends(get_current_user),
):
    cache_key = f"cache:stats:municipality:{slug}"
    cached = await cache_get(request, cache_key)
    if cached is not None:
        return cached

    df = _prepare_market_df()
    if df is None or df.empty or "municipality" not in df.columns:
        raise HTTPException(status_code=404, detail="Municipality not found")

    municipality_df = _find_municipality_frame(df, slug)
    if municipality_df.empty:
        raise HTTPException(status_code=404, detail="Municipality not found")

    municipality_name = str(municipality_df["municipality"].iloc[0])
    municipality_slug_value = str(municipality_df["_municipality_slug"].iloc[0])
    region = (
        _mode_or_none(municipality_df["statistical_region"])
        if "statistical_region" in municipality_df.columns
        else None
    )

    year_trend = []
    if municipality_df["_year"].notna().any():
        grouped = sorted(
            municipality_df[municipality_df["_year"].notna()].groupby("_year"), key=lambda item: int(item[0])
        )
        year_trend = _summarize_yearly(grouped)

    property_type_mix = []
    if "property_type" in municipality_df.columns:
        counts = municipality_df["property_type"].fillna("unknown").value_counts()
        total = int(counts.sum()) or 1
        property_type_mix = [
            {
                "property_type": str(property_type),
                "count": int(count),
                "share": round(int(count) / total, 4),
            }
            for property_type, count in counts.items()
        ]

    recent_frame = municipality_df.copy()
    if recent_frame["_sale_date"].notna().any():
        recent_frame = recent_frame.sort_values(["_sale_date", "price_eur"], ascending=[False, False])
    elif recent_frame["_year"].notna().any():
        recent_frame = recent_frame.sort_values(["_year", "price_eur"], ascending=[False, False])
    else:
        recent_frame = recent_frame.sort_index(ascending=False)
    recent_transactions = [_serialize_price_row(row) for _, row in recent_frame.head(12).iterrows()]

    related_municipalities = []
    region_rank_by_activity = None
    region_rank_by_price = None
    if region:
        region_df = df[df["statistical_region"] == region]
        region_stats = [_municipality_stats(group) for _, group in region_df.groupby("_municipality_slug")]
        region_stats.sort(key=lambda item: item["count"], reverse=True)
        related_municipalities = [item for item in region_stats if item["slug"] != municipality_slug_value][:6]

        for index, item in enumerate(region_stats, start=1):
            if item["slug"] == municipality_slug_value:
                region_rank_by_activity = index
                break

        price_sorted = [
            item
            for item in sorted(
                region_stats,
                key=lambda item: (
                    item["median_price_per_m2"] is not None,
                    item["median_price_per_m2"] or 0,
                    item["count"],
                ),
                reverse=True,
            )
            if item["median_price_per_m2"] is not None
        ]
        for index, item in enumerate(price_sorted, start=1):
            if item["slug"] == municipality_slug_value:
                region_rank_by_price = index
                break

    result = {
        "municipality": municipality_name,
        "slug": municipality_slug_value,
        "region": region,
        "overview": {
            "count": int(len(municipality_df)),
            "avg_price": _round_or_none(municipality_df["price_eur"].mean())
            if "price_eur" in municipality_df.columns
            else None,
            "median_price": _round_or_none(municipality_df["price_eur"].median())
            if "price_eur" in municipality_df.columns
            else None,
            "avg_price_per_m2": _round_or_none(municipality_df["_price_per_m2"].dropna().mean()),
            "median_price_per_m2": _round_or_none(municipality_df["_price_per_m2"].dropna().median()),
            "avg_area": _round_or_none(municipality_df["_area"].dropna().mean(), 1),
            "median_area": _round_or_none(municipality_df["_area"].dropna().median(), 1),
            "latest_year": str(municipality_df["_year"].dropna().max())
            if municipality_df["_year"].notna().any()
            else None,
            "earliest_year": str(municipality_df["_year"].dropna().min())
            if municipality_df["_year"].notna().any()
            else None,
        },
        "market_position": {
            "region_rank_by_activity": region_rank_by_activity,
            "region_rank_by_price_per_m2": region_rank_by_price,
        },
        "year_trend": year_trend,
        "property_type_mix": property_type_mix,
        "recent_transactions": recent_transactions,
        "related_municipalities": related_municipalities,
    }
    await cache_set(request, cache_key, result)
    return result


@router.get("/comparables")
async def comparables(
    request: Request,
    municipality: str = Query(..., min_length=1),
    property_type: str = Query(..., min_length=1),
    size_m2: float = Query(..., gt=1),
    year_built: int | None = Query(None, ge=1800, le=2030),
    price_eur: float | None = Query(None, gt=1),
    limit: int = Query(8, ge=3, le=20),
    _user: User = Depends(get_current_user),
):
    cache_key = f"cache:stats:comparables:{municipality_slug(municipality)}:{property_type}:{size_m2}:{year_built}:{price_eur}:{limit}"
    cached = await cache_get(request, cache_key)
    if cached is not None:
        return cached

    df = _prepare_market_df(property_type=property_type)
    target_slug = municipality_slug(municipality)
    target = {
        "municipality": municipality,
        "slug": target_slug,
        "property_type": property_type,
        "size_m2": round(size_m2, 1),
        "year_built": year_built,
        "price_eur": _round_or_none(price_eur),
        "region": None,
    }

    if df is None or df.empty:
        return {"target": target, "summary": {"count": 0, "municipality_matched": False}, "items": []}

    target_df = _find_municipality_frame(df, municipality)
    municipality_matched = not target_df.empty
    region = (
        _mode_or_none(target_df["statistical_region"])
        if municipality_matched and "statistical_region" in target_df.columns
        else None
    )
    canonical_municipality = str(target_df["municipality"].iloc[0]) if municipality_matched else municipality
    target.update(
        {"municipality": canonical_municipality, "slug": municipality_slug(canonical_municipality), "region": region}
    )

    candidates = df[df["_area"].notna() & (df["_area"] > 0)].copy()
    if region:
        regional_candidates = candidates[candidates["statistical_region"] == region].copy()
        if len(regional_candidates) >= limit:
            candidates = regional_candidates

    candidates["area_delta_ratio"] = (candidates["_area"] - size_m2).abs() / max(size_m2, 1)
    close_candidates = candidates[candidates["area_delta_ratio"] <= 0.35]
    medium_candidates = candidates[candidates["area_delta_ratio"] <= 0.55]
    if len(close_candidates) >= limit:
        candidates = close_candidates
    elif len(medium_candidates) >= limit:
        candidates = medium_candidates

    if year_built is not None and "year_built" in candidates.columns:
        candidate_years = pd.to_numeric(candidates["year_built"], errors="coerce")
        candidates["year_delta_ratio"] = ((candidate_years - year_built).abs() / 40).fillna(0.35)
    else:
        candidates["year_delta_ratio"] = 0.15

    if price_eur is not None and "price_eur" in candidates.columns:
        candidates["price_delta_ratio"] = (
            (pd.to_numeric(candidates["price_eur"], errors="coerce") - price_eur).abs() / price_eur
        ).fillna(0.25)
    else:
        candidates["price_delta_ratio"] = 0.0

    candidates["location_bonus"] = np.where(candidates["_municipality_slug"] == target["slug"], 0.18, 0.0)
    if region:
        candidates["location_bonus"] += np.where(candidates["statistical_region"] == region, 0.08, 0.0)

    raw_similarity = (
        1.0
        - candidates["area_delta_ratio"].clip(0, 1.4) * 0.52
        - candidates["year_delta_ratio"].clip(0, 1.0) * 0.18
        - candidates["price_delta_ratio"].clip(0, 1.0) * 0.14
        + candidates["location_bonus"]
    )
    candidates["similarity_score"] = raw_similarity.clip(0.01, 0.99)

    candidates = candidates.sort_values(
        ["similarity_score", "area_delta_ratio", "_price_per_m2"],
        ascending=[False, True, False],
    ).head(limit)

    items = []
    for _, row in candidates.iterrows():
        item = _serialize_price_row(row)
        item["similarity_score"] = _round_or_none(row.get("similarity_score"), 3)
        item["size_delta_m2"] = _round_or_none(abs((row.get("_area") or 0) - size_m2), 1)
        if price_eur is not None and row.get("price_eur") is not None:
            item["price_delta_eur"] = _round_or_none(row["price_eur"] - price_eur)
            item["price_delta_pct"] = _round_or_none(((row["price_eur"] - price_eur) / price_eur) * 100, 2)
        else:
            item["price_delta_eur"] = None
            item["price_delta_pct"] = None
        items.append(item)

    result = {
        "target": target,
        "summary": {
            "count": int(len(items)),
            "municipality_matched": municipality_matched,
            "region": region,
            "median_price": _round_or_none(candidates["price_eur"].median())
            if "price_eur" in candidates.columns and not candidates.empty
            else None,
            "median_price_per_m2": _round_or_none(candidates["_price_per_m2"].dropna().median()),
        },
        "items": items,
    }
    await cache_set(request, cache_key, result)
    return result


@router.get("/municipalities-by-region")
async def municipalities_by_region(
    region: str | None = None,
    _user: User = Depends(get_current_user),
):
    """Return {region: [municipality, ...]} from training data."""
    df = _load_df()
    if df is None or "municipality" not in df.columns:
        return [] if region else {}

    if "statistical_region" not in df.columns:
        df["statistical_region"] = df["municipality"].apply(
            lambda m: lookup_region(str(m)) if pd.notna(m) else "neznana"
        )

    mapping = df[["municipality", "statistical_region"]].dropna().drop_duplicates()
    if region:
        filtered = mapping[mapping["statistical_region"].map(lambda value: labels_match(value, region))]
        return [
            {"municipality": format_municipality_label(municipality) or municipality}
            for municipality in sorted(filtered["municipality"].unique().tolist())
        ]

    result: dict[str, list[str]] = {}
    for region, group in mapping.groupby("statistical_region"):
        result[format_region_label(region) or str(region)] = sorted(
            (format_municipality_label(municipality) or municipality) for municipality in group["municipality"].unique().tolist()
        )
    return result


@router.get("/map-overview")
async def map_overview(
    property_type: str | None = None,
    statistical_region: str | None = None,
    year: str | None = None,
    _user: User = Depends(get_current_user),
):
    """Return municipality markers for the overview map without relying on model artifacts."""
    df = _prepare_market_df()
    if df is None or df.empty:
        return {"municipalities": [], "count": 0, "meta": {"reason": "no_train_dataset"}}

    if property_type and "property_type" in df.columns:
        df = df[df["property_type"].astype(str).str.casefold() == str(property_type).casefold()]

    if statistical_region and "statistical_region" in df.columns:
        df = df[df["statistical_region"].map(lambda value: labels_match(value, statistical_region))]

    if year and "_year" in df.columns:
        df = df[df["_year"].astype(str) == str(year)]

    if df.empty:
        return {"municipalities": [], "count": 0, "meta": {"reason": "no_matches"}}

    map_df, reason = _prepare_map_coordinates(df)
    if map_df.empty:
        return {"municipalities": [], "count": 0, "meta": {"reason": reason or "no_coordinates"}}

    municipalities = []
    group_key = "_municipality_slug" if "_municipality_slug" in map_df.columns else "municipality"
    for _, group in map_df.groupby(group_key):
        municipalities.append(
            {
                "municipality": (
                    format_municipality_label(group["municipality"].iloc[0]) if "municipality" in group.columns else "unknown"
                ),
                "slug": str(group["_municipality_slug"].iloc[0])
                if "_municipality_slug" in group.columns
                else municipality_slug(group["municipality"].iloc[0]),
                "region": (
                    format_region_label(_mode_or_none(group["statistical_region"]))
                    if "statistical_region" in group.columns
                    else None
                ),
                "count": int(len(group)),
                "lat": _round_or_none(group["_map_lat"].median(), 6),
                "lon": _round_or_none(group["_map_lon"].median(), 6),
                "avg_price": _round_or_none(group["price_eur"].mean()) if "price_eur" in group.columns else None,
                "median_price": _round_or_none(group["price_eur"].median()) if "price_eur" in group.columns else None,
                "avg_price_per_m2": _round_or_none(group["_price_per_m2"].dropna().mean()),
            }
        )

    municipalities.sort(key=lambda item: item["count"], reverse=True)
    return {"municipalities": municipalities, "count": len(municipalities), "meta": {"reason": None}}


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
    df = _prepare_market_df()
    if df is None or df.empty:
        return {"transactions": [], "count": 0, "meta": {"reason": "no_train_dataset"}}

    if property_type and "property_type" in df.columns:
        df = df[df["property_type"].astype(str).str.casefold() == str(property_type).casefold()]

    # Apply filters
    if statistical_region and "statistical_region" in df.columns:
        df = df[df["statistical_region"].map(lambda value: labels_match(value, statistical_region))]
    if municipality and "municipality" in df.columns:
        df = df[df["municipality"].map(lambda value: labels_match(value, municipality))]

    if year and "_year" in df.columns:
        df = df[df["_year"].astype(str) == str(year)]

    if df.empty:
        return {"transactions": [], "count": 0, "meta": {"reason": "no_matches"}}

    map_df, reason = _prepare_map_coordinates(df)
    if map_df.empty:
        return {"transactions": [], "count": 0, "meta": {"reason": reason or "no_coordinates"}}

    # Sample if too many
    if len(map_df) > limit:
        map_df = map_df.sample(n=limit, random_state=42)

    area = _effective_area(map_df)

    # Build result DataFrame vectorized (no iterrows)
    result_df = pd.DataFrame(
        {
            "lat": map_df["_map_lat"].values,
            "lon": map_df["_map_lon"].values,
        }
    )

    result_df["price_eur"] = map_df["price_eur"].values if "price_eur" in map_df.columns else np.nan
    result_df["size_m2"] = map_df["size_m2"].values if "size_m2" in map_df.columns else np.nan
    result_df["municipality"] = (
        map_df["municipality"].map(lambda value: format_municipality_label(value) or "").astype(str).values
        if "municipality" in map_df.columns
        else ""
    )
    result_df["property_type"] = (
        map_df["property_type"].astype(str).values if "property_type" in map_df.columns else ""
    )
    result_df["rooms"] = map_df["rooms"].values if "rooms" in map_df.columns else np.nan

    # Year column — pick first available
    year_src = None
    for col in ["_year", "transaction_year", "source_label"]:
        if col in map_df.columns:
            year_src = col
            break
    result_df["year"] = map_df[year_src].astype(str).str[:4].values if year_src else ""

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

    return {"transactions": transactions, "count": len(transactions), "meta": {"reason": None}}
