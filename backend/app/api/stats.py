"""Statistics routes: overview, regions, distribution, trend."""

import os

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services.regions_service import lookup_region

router = APIRouter(prefix="/stats", tags=["stats"])

TRAIN_CSV = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "raw", "train.csv"
)


def _load_df(property_type: str | None = None) -> pd.DataFrame | None:
    if not os.path.exists(TRAIN_CSV):
        return None
    df = pd.read_csv(TRAIN_CSV)
    if property_type and "property_type" in df.columns:
        df = df[df["property_type"] == property_type]
    return df


@router.get("/overview")
async def overview(
    property_type: str | None = None,
    _user: User = Depends(get_current_user),
):
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
        valid = df[(df["size_m2"] > 0)]
        if not valid.empty:
            result["avg_price_per_m2"] = round(float((valid["price_eur"] / valid["size_m2"]).mean()), 2)

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
        result["property_types"] = [
            {"type": t, "count": int(c)} for t, c in types.items()
        ]

    return result


@router.get("/regions")
async def regions_stats(
    _user: User = Depends(get_current_user),
):
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
            valid = group[group["size_m2"] > 0]
            if not valid.empty:
                entry["avg_price_per_m2"] = round(float((valid["price_eur"] / valid["size_m2"]).mean()), 2)
        results.append(entry)

    return sorted(results, key=lambda x: x["count"], reverse=True)


@router.get("/price-distribution")
async def price_distribution(
    bins: int = Query(20, ge=5, le=100),
    property_type: str | None = None,
    _user: User = Depends(get_current_user),
):
    df = _load_df(property_type)
    if df is None or "price_eur" not in df.columns or df.empty:
        return {"bins": [], "counts": [], "bin_labels": []}

    prices = df["price_eur"].dropna()
    if prices.empty:
        return {"bins": [], "counts": [], "bin_labels": []}

    counts_arr, bin_edges = np.histogram(prices, bins=bins)
    bin_labels = [f"{int(bin_edges[i])}-{int(bin_edges[i+1])}" for i in range(len(counts_arr))]

    return {
        "bins": [float(b) for b in bin_edges],
        "counts": [int(c) for c in counts_arr],
        "bin_labels": bin_labels,
    }


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
            "by_type": {},
        }
        if "property_type" in group.columns:
            for pt, pt_group in group.groupby("property_type"):
                entry["by_type"][pt] = {
                    "count": len(pt_group),
                    "avg_price": round(float(pt_group["price_eur"].mean()), 2) if "price_eur" in pt_group.columns else None,
                }
        results.append(entry)

    return results
