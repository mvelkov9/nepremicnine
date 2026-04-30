"""Statistics routes: overview, regions, distribution, trend."""

import logging
import math
import os
import threading
from collections.abc import Iterable

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services.regions_service import CANONICAL_REGION_LOOKUP, CANONICAL_REGION_ROWS, lookup_region
from app.utils.cache import cache_get
from app.utils.cache import cache_set as _base_cache_set
from app.utils.municipality import municipality_slug, normalize_municipality_name
from app.utils.slovenian_labels import (
    format_municipality_label,
    format_region_label,
    is_unknown_label,
    labels_match,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stats", tags=["stats"])

RAW_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "raw",
)
TRAIN_CSV = os.path.join(RAW_DATA_DIR, "train.csv")

_STATS_CSV_COLUMNS = {
    "source_row_key",
    "size_m2",
    "rooms",
    "num_prostori",
    "has_klet",
    "has_garaza",
    "has_terasa",
    "has_shramba",
    "year_built",
    "floor",
    "ime_ko",
    "naselje",
    "longitude",
    "latitude",
    "novogradnja",
    "stavba_je_dokoncana",
    "uporabna_povrsina",
    "lega_v_stavbi",
    "ddv_vkljucen",
    "transaction_quarter",
    "transaction_month",
    "transaction_season",
    "municipality",
    "property_type",
    "price_eur",
    "vrsta_kupoprodajnega_posla",
    "municipality_normalized",
    "statistical_region",
    "building_age",
    "parcela_m2",
    "vrsta_zemljisca",
    "source_label",
    "transaction_year",
    "transaction_date",
    "sale_date",
    "datum_sklenitve",
    "kn_ggo_section",
    "parcela_namenska_raba",
}

_RAW_DF_CACHE: dict[str, object] = {"mtime": None, "size": None, "df": None}
_PREPARED_DF_CACHE: dict[str, object] = {
    "path": None,
    "mtime": None,
    "size": None,
    "shape": None,
    "columns": None,
    "df": None,
}
_CACHE_LOCK = threading.RLock()
_CANONICAL_REGION_TOTAL = len(CANONICAL_REGION_ROWS)
_CANONICAL_MUNICIPALITY_KEYS = set(CANONICAL_REGION_LOOKUP)
STATS_CACHE_TTL = 86400
STATS_CACHE_CONTROL = f"private, max-age={STATS_CACHE_TTL}"


async def cache_set(request: Request, key: str, value, ttl: int = STATS_CACHE_TTL) -> None:
    await _base_cache_set(request, key, value, ttl=ttl)


def _set_stats_cache_headers(response: Response | None) -> None:
    if response is not None:
        response.headers["Cache-Control"] = STATS_CACHE_CONTROL


def _resolve_train_csv_path() -> str:
    env_path = os.getenv("STATS_TRAIN_CSV")
    if env_path:
        return os.path.abspath(env_path)
    return TRAIN_CSV


def _first_present(*values: object) -> object | None:
    for value in values:
        if value is None:
            continue
        if pd.isna(value):
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


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


def _training_file_signature() -> tuple[str, int | None, int | None]:
    train_csv = _resolve_train_csv_path()
    try:
        stats = os.stat(train_csv)
    except OSError:
        return train_csv, None, None
    return train_csv, int(stats.st_mtime_ns), int(stats.st_size)


def _stats_cache_namespace() -> str:
    train_csv, mtime_ns, size_bytes = _training_file_signature()
    file_token = os.path.basename(train_csv) or "train.csv"
    return f"{file_token}:{mtime_ns if mtime_ns is not None else 'missing'}:{size_bytes if size_bytes is not None else 'missing'}"


def _stats_cache_prefix(name: str) -> str:
    return f"cache:stats:{name}:{_stats_cache_namespace()}"


def _load_df(property_type: str | None = None) -> pd.DataFrame | None:
    train_csv, mtime_ns, size_bytes = _training_file_signature()
    if mtime_ns is None:
        with _CACHE_LOCK:
            _RAW_DF_CACHE["mtime"] = None
            _RAW_DF_CACHE["size"] = None
            _RAW_DF_CACHE["df"] = None
        return None

    needs_reload = (
        _RAW_DF_CACHE.get("mtime") != mtime_ns
        or _RAW_DF_CACHE.get("size") != size_bytes
        or _RAW_DF_CACHE.get("df") is None
    )
    if needs_reload:
        # Prevent multiple concurrent requests from loading the same large CSV at once.
        with _CACHE_LOCK:
            if (
                _RAW_DF_CACHE.get("mtime") != mtime_ns
                or _RAW_DF_CACHE.get("size") != size_bytes
                or _RAW_DF_CACHE.get("df") is None
            ):
                _RAW_DF_CACHE["mtime"] = mtime_ns
                _RAW_DF_CACHE["size"] = size_bytes
                _RAW_DF_CACHE["df"] = pd.read_csv(
                    train_csv,
                    usecols=lambda col: col in _STATS_CSV_COLUMNS,
                    low_memory=False,
                )
    df = _RAW_DF_CACHE.get("df")
    if not isinstance(df, pd.DataFrame):
        return None
    if property_type and "property_type" in df.columns:
        normalized = str(property_type).strip().casefold()
        return df[df["property_type"].astype(str).str.casefold() == normalized]
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


def _year_bounds(df: pd.DataFrame) -> tuple[str | None, str | None]:
    if "_year" not in df.columns:
        return None, None
    years = pd.to_numeric(df["_year"], errors="coerce").dropna()
    if years.empty:
        return None, None
    return str(int(years.min())), str(int(years.max()))


def _extract_year_series(df: pd.DataFrame) -> pd.Series:
    if "_year" in df.columns:
        extracted = df["_year"].astype("string").str.extract(r"(\d{4})", expand=False)
        if extracted.notna().any():
            return extracted

    for year_col in [
        "transaction_year",
        "transaction_date",
        "sale_date",
        "datum_sklenitve",
        "source_label",
        "year",
        "sale_year",
    ]:
        if year_col not in df.columns:
            continue
        extracted = df[year_col].astype("string").str.extract(r"(\d{4})", expand=False)
        if extracted.notna().any():
            return extracted

    return pd.Series(pd.NA, index=df.index, dtype="string")


def _normalize_location_name(value: object | None) -> str:
    if value is None or pd.isna(value):
        return "unknown"
    text = " ".join(str(value).strip().split())
    return text.casefold() if text else "unknown"


def _price_band_key(value: float | int | None, thresholds: dict[str, float] | None) -> str | None:
    if value is None or pd.isna(value) or not thresholds:
        return None
    numeric = float(value)
    if numeric <= thresholds["low_max"]:
        return "low"
    if numeric <= thresholds["mid_max"]:
        return "mid"
    return "high"


def _build_price_band_meta(values: pd.Series) -> dict | None:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    if numeric.empty:
        return None

    low_max = float(numeric.quantile(0.33))
    mid_max = float(numeric.quantile(0.66))
    max_value = float(numeric.max())
    min_value = float(numeric.min())

    thresholds = {
        "min": round(min_value, 2),
        "low_max": round(low_max, 2),
        "mid_max": round(mid_max, 2),
        "max": round(max_value, 2),
    }
    bands = numeric.map(lambda value: _price_band_key(value, thresholds))

    return {
        "metric": "price_per_m2",
        "unit": "eur_per_m2",
        "thresholds": thresholds,
        "counts": {
            "low": int((bands == "low").sum()),
            "mid": int((bands == "mid").sum()),
            "high": int((bands == "high").sum()),
        },
    }


def _stable_transaction_key(row: pd.Series) -> str:
    municipality = municipality_slug(str(_first_present(row.get("municipality"), "unknown")))
    year = str(_first_present(row.get("_year"), row.get("source_label"), "na"))
    price = int(round(float(_first_present(row.get("price_eur"), 0))))
    area = int(round(float(_first_present(row.get("_area"), 0))))
    lat = int(round(float(_first_present(row.get("_map_lat"), row.get("latitude"), 0)) * 10000))
    lon = int(round(float(_first_present(row.get("_map_lon"), row.get("longitude"), 0)) * 10000))
    return f"{municipality}:{year}:{price}:{area}:{lat}:{lon}"


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
    train_csv = _resolve_train_csv_path()
    df = _load_df()
    if df is None or df.empty:
        return None
    mtime = _RAW_DF_CACHE.get("mtime")
    size = _RAW_DF_CACHE.get("size")
    shape = tuple(df.shape)
    columns = tuple(df.columns)
    cached_path = _PREPARED_DF_CACHE.get("path")
    cached_mtime = _PREPARED_DF_CACHE.get("mtime")
    cached_size = _PREPARED_DF_CACHE.get("size")
    cached_shape = _PREPARED_DF_CACHE.get("shape")
    cached_columns = _PREPARED_DF_CACHE.get("columns")
    cached_df = _PREPARED_DF_CACHE.get("df")
    if (
        cached_path != train_csv
        or cached_mtime != mtime
        or cached_size != size
        or cached_shape != shape
        or cached_columns != columns
        or cached_df is None
    ):
        with _CACHE_LOCK:
            cached_path = _PREPARED_DF_CACHE.get("path")
            cached_mtime = _PREPARED_DF_CACHE.get("mtime")
            cached_size = _PREPARED_DF_CACHE.get("size")
            cached_shape = _PREPARED_DF_CACHE.get("shape")
            cached_columns = _PREPARED_DF_CACHE.get("columns")
            cached_df = _PREPARED_DF_CACHE.get("df")
            if (
                cached_path != train_csv
                or cached_mtime != mtime
                or cached_size != size
                or cached_shape != shape
                or cached_columns != columns
                or cached_df is None
            ):
                frame = _ensure_regions(df.copy())

                if "municipality" in frame.columns:
                    frame["municipality"] = frame["municipality"].map(
                        lambda value: format_municipality_label(value) or "unknown"
                    )
                    frame["_municipality_slug"] = frame["municipality"].map(municipality_slug)
                    frame["_municipality_normalized"] = frame["municipality"].map(normalize_municipality_name)
                    frame["_municipality_known"] = frame["_municipality_normalized"].isin(_CANONICAL_MUNICIPALITY_KEYS)

                if "naselje" in frame.columns:
                    frame["naselje"] = (
                        frame["naselje"]
                        .fillna("unknown")
                        .map(lambda value: " ".join(str(value).strip().split()) or "unknown")
                    )
                    frame["_naselje_normalized"] = frame["naselje"].map(_normalize_location_name)

                if "statistical_region" in frame.columns:
                    frame["statistical_region"] = frame["statistical_region"].map(
                        lambda value: format_region_label(value) or "Neznana"
                    )

                if "property_type" in frame.columns:
                    frame["_property_type_key"] = frame["property_type"].fillna("").astype(str).str.casefold()

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

                date_col = next(
                    (col for col in ["transaction_date", "sale_date", "datum_sklenitve"] if col in frame.columns),
                    None,
                )
                if date_col:
                    frame["_sale_date"] = pd.to_datetime(frame[date_col], errors="coerce")
                else:
                    frame["_sale_date"] = pd.NaT

                _PREPARED_DF_CACHE["path"] = train_csv
                _PREPARED_DF_CACHE["mtime"] = mtime
                _PREPARED_DF_CACHE["size"] = size
                _PREPARED_DF_CACHE["shape"] = shape
                _PREPARED_DF_CACHE["columns"] = columns
                _PREPARED_DF_CACHE["df"] = frame

    cached = _PREPARED_DF_CACHE["df"]
    if not isinstance(cached, pd.DataFrame):
        return None

    if property_type and "property_type" in cached.columns:
        normalized = str(property_type).strip().casefold()
        if "_property_type_key" in cached.columns:
            return cached[cached["_property_type_key"] == normalized]
        return cached[cached["property_type"].astype(str).str.casefold() == normalized]
    return cached


def _known_municipality_mask(df: pd.DataFrame) -> pd.Series:
    if "_municipality_known" in df.columns:
        return df["_municipality_known"].fillna(False).astype(bool)
    if "municipality" in df.columns:
        return ~df["municipality"].map(is_unknown_label)
    return pd.Series(False, index=df.index, dtype=bool)


def _viewer_frame(df: pd.DataFrame) -> pd.DataFrame:
    if "municipality" not in df.columns:
        return df
    return df[_known_municipality_mask(df)]


def _canonical_municipality_coverage(df: pd.DataFrame) -> dict[str, int]:
    if "municipality" not in df.columns:
        return {
            "present": 0,
            "official_total": _CANONICAL_REGION_TOTAL,
            "unresolved_rows": 0,
            "noncanonical_rows": 0,
            "noncanonical_labels": [],
        }

    known = df[_known_municipality_mask(df)]
    present = int(known["_municipality_slug"].nunique()) if "_municipality_slug" in known.columns else 0
    unresolved_rows = int((~_known_municipality_mask(df)).sum())
    noncanonical_labels: list[dict[str, int | str]] = []
    noncanonical_rows = 0
    if "_municipality_normalized" in df.columns:
        noncanonical_mask = (~df["_municipality_normalized"].isin(_CANONICAL_MUNICIPALITY_KEYS)) & ~df[
            "municipality"
        ].map(is_unknown_label)
        noncanonical_rows = int(noncanonical_mask.sum())
        noncanonical_counts = df.loc[noncanonical_mask, "municipality"].astype(str).value_counts()
        noncanonical_labels = [
            {"label": str(label), "count": int(count)} for label, count in noncanonical_counts.head(12).items()
        ]
    return {
        "present": present,
        "official_total": _CANONICAL_REGION_TOTAL,
        "unresolved_rows": unresolved_rows,
        "noncanonical_rows": noncanonical_rows,
        "noncanonical_labels": noncanonical_labels,
    }


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
        "id": _stable_transaction_key(row),
        "municipality": format_municipality_label(row.get("municipality")) or row.get("municipality"),
        "slug": _first_present(row.get("_municipality_slug"), municipality_slug(row.get("municipality"))),
        "region": format_region_label(row.get("statistical_region")) or row.get("statistical_region"),
        "property_type": row.get("property_type"),
        "price_eur": _round_or_none(row.get("price_eur")),
        "size_m2": _round_or_none(row.get("_area"), 1),
        "uporabna_povrsina": _round_or_none(row.get("uporabna_povrsina"), 1),
        "price_per_m2": _round_or_none(row.get("_price_per_m2")),
        "year": str(row.get("_year")) if pd.notna(row.get("_year")) else None,
        "source_label": row.get("source_label"),
        "year_built": int(row["year_built"]) if "year_built" in row.index and pd.notna(row["year_built"]) else None,
        "rooms": _round_or_none(row.get("rooms"), 1),
        "floor": _round_or_none(row.get("floor"), 0),
        "num_prostori": _round_or_none(row.get("num_prostori"), 0),
        "lega_v_stavbi": row.get("lega_v_stavbi"),
        "lat": _round_or_none(_first_present(row.get("_map_lat"), row.get("latitude")), 6),
        "lon": _round_or_none(_first_present(row.get("_map_lon"), row.get("longitude")), 6),
        "novogradnja": int(row["novogradnja"]) if "novogradnja" in row.index and pd.notna(row["novogradnja"]) else None,
        "has_garaza": int(row["has_garaza"]) if "has_garaza" in row.index and pd.notna(row["has_garaza"]) else None,
        "has_klet": int(row["has_klet"]) if "has_klet" in row.index and pd.notna(row["has_klet"]) else None,
        "has_terasa": int(row["has_terasa"]) if "has_terasa" in row.index and pd.notna(row["has_terasa"]) else None,
        "has_shramba": int(row["has_shramba"]) if "has_shramba" in row.index and pd.notna(row["has_shramba"]) else None,
        "stavba_je_dokoncana": int(row["stavba_je_dokoncana"])
        if "stavba_je_dokoncana" in row.index and pd.notna(row["stavba_je_dokoncana"])
        else None,
        "ddv_vkljucen": int(row["ddv_vkljucen"])
        if "ddv_vkljucen" in row.index and pd.notna(row["ddv_vkljucen"])
        else None,
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
            format_region_label(_mode_or_none(group["statistical_region"]))
            if "statistical_region" in group.columns
            else None
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


def _municipality_match_mask(df: pd.DataFrame, slug_or_name: str) -> pd.Series:
    if df.empty:
        return pd.Series(False, index=df.index, dtype=bool)

    slug = municipality_slug(slug_or_name)
    if "_municipality_slug" in df.columns:
        return (df["_municipality_slug"] == slug).fillna(False)
    if "municipality" in df.columns:
        return df["municipality"].map(municipality_slug) == slug
    return pd.Series(False, index=df.index, dtype=bool)


def _clean_query_value(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_search_series(series: pd.Series) -> pd.Series:
    return series.fillna("").map(lambda value: normalize_municipality_name(str(value)))


def _apply_market_filters(
    df: pd.DataFrame,
    *,
    property_type: str | None = None,
    region: str | None = None,
    municipality: str | None = None,
    year: str | None = None,
    search: str | None = None,
    viewer_only: bool = True,
) -> pd.DataFrame:
    frame = _viewer_frame(df) if viewer_only else df

    clean_property_type = _clean_query_value(property_type)
    clean_region = _clean_query_value(region)
    clean_municipality = _clean_query_value(municipality)
    clean_year = _clean_query_value(year)
    clean_search = _clean_query_value(search)

    if clean_property_type and "property_type" in frame.columns:
        property_key = clean_property_type.casefold()
        if "_property_type_key" in frame.columns:
            frame = frame[frame["_property_type_key"] == property_key]
        else:
            frame = frame[frame["property_type"].astype(str).str.casefold() == property_key]

    if clean_region and "statistical_region" in frame.columns:
        frame = frame[frame["statistical_region"].map(lambda value: labels_match(value, clean_region))]

    if clean_municipality and "municipality" in frame.columns:
        clean_slug = municipality_slug(clean_municipality)
        if "_municipality_slug" in frame.columns:
            frame = frame[frame["_municipality_slug"] == clean_slug]
        else:
            frame = frame[frame["municipality"].map(lambda value: labels_match(value, clean_municipality))]

    if clean_year and "_year" in frame.columns:
        frame = frame[frame["_year"].astype(str) == clean_year]

    if clean_search:
        search_key = normalize_municipality_name(clean_search)
        search_columns = []
        for column in ["municipality", "statistical_region", "property_type", "naselje", "_year"]:
            if column in frame.columns:
                search_columns.append(_normalize_search_series(frame[column]))
        if search_columns:
            haystack = search_columns[0]
            for column in search_columns[1:]:
                haystack = haystack + " " + column
            frame = frame[haystack.str.contains(search_key, na=False)]

    return frame


def _explorer_cache_key(
    prefix: str,
    *,
    property_type: str | None,
    region: str | None,
    municipality: str | None,
    year: str | None,
    search: str | None = None,
    page: int,
    page_size: int,
    sort: str,
    order: str,
) -> str:
    return (
        f"{_stats_cache_prefix(prefix)}:"
        f"{property_type or 'all'}:{region or 'all'}:{municipality_slug(municipality) if municipality else 'all'}:"
        f"{year or 'all'}:{(search or '').strip().casefold() or 'all'}:{page}:{page_size}:{sort}:{order}"
    )


def warm_market_data_cache() -> None:
    try:
        source = _resolve_train_csv_path()
        logger.info("Starting stats dataset warmup source=%s", source)
        df = _prepare_market_df()
        logger.info("Completed stats dataset warmup rows=%s", 0 if df is None else len(df))
    except Exception:
        logger.exception("Stats dataset warmup failed")


def _sort_frame_for_explorer(
    frame: pd.DataFrame,
    *,
    sort: str | None,
    order: str | None,
    default: list[str],
) -> pd.DataFrame:
    clean_order = str(order or "desc").lower()
    ascending = clean_order == "asc"
    mappings = {
        "municipality": ["municipality", "_year", "price_eur"],
        "region": ["region", "statistical_region", "municipality", "_year"],
        "property_type": ["property_type", "_year", "price_eur"],
        "year": ["_year", "price_eur"],
        "price_eur": ["price_eur", "_year"],
        "price_per_m2": ["_price_per_m2", "_year", "price_eur"],
        "size_m2": ["_area", "_year", "price_eur"],
        "count": ["count", "municipality"],
        "median_price": ["median_price", "count", "municipality"],
        "median_price_per_m2": ["median_price_per_m2", "count", "municipality"],
        "avg_price_per_m2": ["avg_price_per_m2", "count", "municipality"],
        "name": ["municipality", "region"],
    }
    candidates = mappings.get(str(sort or "").strip().casefold(), default)
    columns = [column for column in candidates if column in frame.columns]
    if not columns:
        return frame
    return frame.sort_values(
        columns,
        ascending=[ascending] * len(columns),
        na_position="last",
        kind="mergesort",
    )


def _build_explorer_response(
    *,
    items: list[dict],
    total: int,
    page: int,
    page_size: int,
    filters: dict[str, str | None],
    sort: str,
    order: str,
) -> dict:
    pages = math.ceil(total / page_size) if total > 0 else 0
    return {
        "items": items,
        "total": int(total),
        "page": int(page),
        "page_size": int(page_size),
        "pages": int(pages),
        "filters": filters,
        "sort": sort,
        "order": order,
    }


def _empty_overview_payload() -> dict:
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


def _build_overview_payload(df: pd.DataFrame | None) -> dict:
    if df is None or df.empty:
        return _empty_overview_payload()

    result = {
        "total_records": len(df),
        "avg_price": _round_or_none(df["price_eur"].mean()) if "price_eur" in df.columns else None,
        "median_price": _round_or_none(df["price_eur"].median()) if "price_eur" in df.columns else None,
        "min_price": _round_or_none(df["price_eur"].min()) if "price_eur" in df.columns else None,
        "max_price": _round_or_none(df["price_eur"].max()) if "price_eur" in df.columns else None,
        "std_price": _round_or_none(df["price_eur"].std()) if "price_eur" in df.columns else None,
        "avg_area": _round_or_none(df["size_m2"].mean()) if "size_m2" in df.columns else None,
        "median_area": _round_or_none(df["size_m2"].median()) if "size_m2" in df.columns else None,
        "avg_price_per_m2": None,
        "regions_count": int(df["statistical_region"].nunique()) if "statistical_region" in df.columns else None,
        "top_municipalities": [],
        "property_types": [],
    }

    if "year_built" in df.columns:
        yb = pd.to_numeric(df["year_built"], errors="coerce").dropna()
        if not yb.empty:
            result["year_built_avg"] = round(float(yb.mean()), 1)
            result["year_built_min"] = int(yb.min())
            result["year_built_max"] = int(yb.max())

    years = _extract_year_series(df).dropna()
    if not years.empty:
        result["data_years"] = sorted(years.unique().tolist())

    if "price_eur" in df.columns and "size_m2" in df.columns:
        tmp = df[["price_eur"]].copy()
        tmp["_area"] = _effective_area(df)
        valid = tmp.dropna()
        valid = valid[valid["_area"] > 0]
        if not valid.empty:
            result["avg_price_per_m2"] = _round_or_none((valid["price_eur"] / valid["_area"]).mean())

    if "municipality" in df.columns:
        muni_groups = df.groupby("municipality")
        muni_stats = []
        for name, group in muni_groups:
            entry = {"name": name, "count": len(group)}
            if "price_eur" in group.columns:
                entry["avg_price"] = _round_or_none(group["price_eur"].mean())
            muni_stats.append(entry)
        muni_stats.sort(key=lambda x: x["count"], reverse=True)
        result["top_municipalities"] = muni_stats

    if "property_type" in df.columns:
        types = df["property_type"].value_counts()
        result["property_types"] = [{"type": t, "count": int(c)} for t, c in types.items()]

    return result


def _build_regions_stats_payload(df: pd.DataFrame | None) -> list[dict]:
    if df is None or df.empty or "statistical_region" not in df.columns:
        return []

    results = []
    for region_name, group in df.groupby("statistical_region"):
        entry = {
            "region": format_region_label(region_name) or region_name,
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

    return sorted(results, key=lambda x: x["count"], reverse=True)


def _build_price_distribution_payload(df: pd.DataFrame | None, bins: int) -> dict:
    if df is None or "price_eur" not in df.columns or df.empty:
        return {"bins": [], "counts": [], "bin_labels": []}

    prices = pd.to_numeric(df["price_eur"], errors="coerce").dropna()
    prices = prices[prices > 0]
    if len(prices) > 1:
        prices = prices[prices <= prices.quantile(0.99)]
    if prices.empty:
        return {"bins": [], "counts": [], "bin_labels": []}

    counts_arr, bin_edges = np.histogram(prices, bins=bins)
    return {
        "bins": [float(b) for b in bin_edges],
        "counts": [int(c) for c in counts_arr],
        "bin_labels": [
            f"{_format_eur(bin_edges[i])}\u2013{_format_eur(bin_edges[i + 1])}" for i in range(len(counts_arr))
        ],
    }


@router.get("/overview")
async def overview(
    request: Request,
    response: Response,
    property_type: str | None = None,
    region: str | None = None,
    municipality: str | None = None,
    year: str | None = None,
    _user: User = Depends(get_current_user),
):
    _set_stats_cache_headers(response)
    cache_key = (
        f"{_stats_cache_prefix('overview')}:"
        f"{property_type or 'all'}:{region or 'all'}:{municipality_slug(municipality) if municipality else 'all'}:{year or 'all'}"
    )
    cached = await cache_get(request, cache_key)
    if cached is not None:
        return cached

    df = _prepare_market_df(property_type)
    if df is not None and not df.empty:
        df = _apply_market_filters(df, region=region, municipality=municipality, year=year)
    result = _build_overview_payload(df)
    await cache_set(request, cache_key, result)
    return result


@router.get("/regions")
async def regions_stats(
    request: Request,
    response: Response,
    property_type: str | None = None,
    region: str | None = None,
    municipality: str | None = None,
    year: str | None = None,
    _user: User = Depends(get_current_user),
):
    _set_stats_cache_headers(response)
    cache_key = (
        f"{_stats_cache_prefix('regions')}:"
        f"{property_type or 'all'}:{region or 'all'}:{municipality_slug(municipality) if municipality else 'all'}:{year or 'all'}"
    )
    cached = await cache_get(request, cache_key)
    if cached is not None:
        return cached

    df = _prepare_market_df(property_type)
    if df is not None and not df.empty:
        df = _apply_market_filters(df, region=region, municipality=municipality, year=year)
    result = _build_regions_stats_payload(df)
    await cache_set(request, cache_key, result)
    return result


@router.get("/price-distribution")
async def price_distribution(
    request: Request,
    response: Response = None,
    bins: int = Query(20, ge=5, le=100),
    property_type: str | None = None,
    region: str | None = None,
    municipality: str | None = None,
    year: str | None = None,
    _user: User = Depends(get_current_user),
):
    _set_stats_cache_headers(response)
    cache_key = (
        f"{_stats_cache_prefix('price-distribution')}:"
        f"{bins}:{property_type or 'all'}:{region or 'all'}:{municipality_slug(municipality) if municipality else 'all'}:{year or 'all'}"
    )
    cached = await cache_get(request, cache_key)
    if cached is not None:
        return cached

    df = _prepare_market_df(property_type)
    if df is not None and not df.empty:
        df = _apply_market_filters(df, region=region, municipality=municipality, year=year)
    result = _build_price_distribution_payload(df, bins=bins)
    await cache_set(request, cache_key, result)
    return result


def _build_trend_payload(df: pd.DataFrame | None) -> list[dict]:
    if df is None or df.empty:
        return []

    year_series = _extract_year_series(df)
    if year_series.dropna().empty:
        return []

    frame = df.copy()
    frame["_trend_year"] = year_series
    results: list[dict] = []

    for year, group in sorted(
        frame[frame["_trend_year"].notna()].groupby("_trend_year"), key=lambda item: int(item[0])
    ):
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


def _empty_market_home_payload(
    *,
    property_type: str | None,
    region: str | None,
    municipality: str | None,
    year: str | None,
) -> dict:
    return {
        "headline": {
            "total_records": 0,
            "municipalities_count": 0,
            "known_municipalities_count": 0,
            "unresolved_municipality_rows": 0,
            "regions_count": 0,
            "avg_price": None,
            "median_price": None,
            "avg_price_per_m2": None,
            "latest_year": None,
            "earliest_year": None,
        },
        "active_property_type": property_type,
        "largest_markets": [],
        "price_leaders": [],
        "region_snapshot": [],
        "latest_sales": [],
        "year_coverage": [],
        "property_type_mix": [],
        "active_filters": {
            "property_type": property_type,
            "region": region,
            "municipality": municipality,
            "year": year,
        },
        "market_coverage": {
            "present": 0,
            "official_total": _CANONICAL_REGION_TOTAL,
            "unresolved_rows": 0,
        },
    }


def _build_market_home_payload(
    df: pd.DataFrame | None,
    *,
    property_type: str | None,
    region: str | None,
    municipality: str | None,
    year: str | None,
) -> dict:
    if df is None or df.empty:
        return _empty_market_home_payload(
            property_type=property_type,
            region=region,
            municipality=municipality,
            year=year,
        )

    viewer_df = _viewer_frame(df)
    coverage = _canonical_municipality_coverage(df)

    municipality_groups = (
        [_municipality_stats(group) for _, group in viewer_df.groupby("_municipality_slug")]
        if "municipality" in viewer_df.columns
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
    if "statistical_region" in viewer_df.columns:
        for region_name, group in viewer_df.groupby("statistical_region"):
            price_per_m2 = group["_price_per_m2"].dropna()
            region_snapshot.append(
                {
                    "region": format_region_label(region_name) or str(region_name),
                    "count": int(len(group)),
                    "avg_price": _round_or_none(group["price_eur"].mean()) if "price_eur" in group.columns else None,
                    "median_price": _round_or_none(group["price_eur"].median())
                    if "price_eur" in group.columns
                    else None,
                    "median_price_per_m2": _round_or_none(price_per_m2.median()),
                }
            )
        region_snapshot.sort(key=lambda item: item["count"], reverse=True)

    latest_frame = (
        viewer_df.dropna(subset=["price_eur"]).copy() if "price_eur" in viewer_df.columns else viewer_df.copy()
    )
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
                "property_type": str(property_name),
                "count": int(count),
                "share": round(int(count) / total, 4),
            }
            for property_name, count in counts.items()
        ]

    earliest_year, latest_year = _year_bounds(df)

    return {
        "headline": {
            "total_records": int(len(df)),
            "municipalities_count": int(coverage["present"]),
            "known_municipalities_count": int(coverage["present"]),
            "unresolved_municipality_rows": int(coverage["unresolved_rows"]),
            "regions_count": int(viewer_df["statistical_region"].nunique())
            if "statistical_region" in viewer_df.columns
            else 0,
            "avg_price": _round_or_none(df["price_eur"].mean()) if "price_eur" in df.columns else None,
            "median_price": _round_or_none(df["price_eur"].median()) if "price_eur" in df.columns else None,
            "avg_price_per_m2": _round_or_none(df["_price_per_m2"].dropna().mean()),
            "latest_year": latest_year,
            "earliest_year": earliest_year,
        },
        "active_property_type": property_type,
        "active_filters": {
            "property_type": property_type,
            "region": region,
            "municipality": municipality,
            "year": year,
        },
        "largest_markets": municipality_groups[:10],
        "price_leaders": price_leaders,
        "region_snapshot": region_snapshot[:8],
        "latest_sales": latest_sales,
        "year_coverage": year_coverage,
        "property_type_mix": property_type_mix,
        "market_coverage": coverage,
    }


@router.get("/trend")
async def trend(
    request: Request,
    response: Response,
    property_type: str | None = None,
    region: str | None = None,
    municipality: str | None = None,
    _user: User = Depends(get_current_user),
):
    _set_stats_cache_headers(response)
    cache_key = (
        f"{_stats_cache_prefix('trend')}:"
        f"{property_type or 'all'}:{region or 'all'}:{municipality_slug(municipality) if municipality else 'all'}"
    )
    cached = await cache_get(request, cache_key)
    if cached is not None:
        return cached

    df = _prepare_market_df(property_type)
    if df is not None and not df.empty:
        df = _apply_market_filters(df, region=region, municipality=municipality)
    results = _build_trend_payload(df)

    await cache_set(request, cache_key, results)
    return results


@router.get("/market-home")
async def market_home(
    request: Request,
    response: Response,
    property_type: str | None = None,
    region: str | None = None,
    municipality: str | None = None,
    year: str | None = None,
    _user: User = Depends(get_current_user),
):
    _set_stats_cache_headers(response)
    cache_key = (
        f"{_stats_cache_prefix('market-home')}:"
        f"{property_type or 'all'}:{region or 'all'}:{municipality_slug(municipality) if municipality else 'all'}:{year or 'all'}"
    )
    cached = await cache_get(request, cache_key)
    if cached is not None:
        return cached

    df = _prepare_market_df(property_type=property_type)
    if df is not None and not df.empty:
        df = _apply_market_filters(
            df,
            region=region,
            municipality=municipality,
            year=year,
            viewer_only=False,
        )
    result = _build_market_home_payload(
        df,
        property_type=property_type,
        region=region,
        municipality=municipality,
        year=year,
    )
    await cache_set(request, cache_key, result)
    return result


@router.get("/transactions")
async def transactions_explorer(
    request: Request,
    response: Response,
    property_type: str | None = None,
    region: str | None = None,
    municipality: str | None = None,
    year: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    sort: str = Query("recent"),
    order: str = Query("desc"),
    _user: User = Depends(get_current_user),
):
    _set_stats_cache_headers(response)
    cache_key = _explorer_cache_key(
        "transactions",
        property_type=property_type,
        region=region,
        municipality=municipality,
        year=year,
        search=search,
        page=page,
        page_size=page_size,
        sort=sort,
        order=order,
    )
    cached = await cache_get(request, cache_key)
    if cached is not None:
        return cached

    df = _prepare_market_df(property_type=property_type)
    if df is None or df.empty:
        result = _build_explorer_response(
            items=[],
            total=0,
            page=page,
            page_size=page_size,
            filters={
                "property_type": property_type,
                "region": region,
                "municipality": municipality,
                "year": year,
                "search": search,
            },
            sort=sort,
            order=order,
        )
        await cache_set(request, cache_key, result)
        return result

    frame = _apply_market_filters(
        df,
        property_type=property_type,
        region=region,
        municipality=municipality,
        year=year,
        search=search,
    )
    frame = _sort_frame_for_explorer(
        frame,
        sort=None if sort == "recent" else sort,
        order=order,
        default=["_sale_date", "_year", "price_eur"],
    )

    total = int(len(frame))
    offset = (page - 1) * page_size
    paged = frame.iloc[offset : offset + page_size]
    items = [_serialize_price_row(row) for _, row in paged.iterrows()]

    result = _build_explorer_response(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        filters={
            "property_type": _clean_query_value(property_type),
            "region": _clean_query_value(region),
            "municipality": _clean_query_value(municipality),
            "year": _clean_query_value(year),
            "search": _clean_query_value(search),
        },
        sort=sort,
        order=order,
    )
    await cache_set(request, cache_key, result)
    return result


@router.get("/municipalities")
async def municipalities_explorer(
    request: Request,
    response: Response,
    property_type: str | None = None,
    region: str | None = None,
    municipality: str | None = None,
    year: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=200),
    sort: str = Query("count"),
    order: str = Query("desc"),
    _user: User = Depends(get_current_user),
):
    _set_stats_cache_headers(response)
    cache_key = _explorer_cache_key(
        "municipalities",
        property_type=property_type,
        region=region,
        municipality=municipality,
        year=year,
        search=search,
        page=page,
        page_size=page_size,
        sort=sort,
        order=order,
    )
    cached = await cache_get(request, cache_key)
    if cached is not None:
        return cached

    df = _prepare_market_df(property_type=property_type)
    if df is None or df.empty:
        result = _build_explorer_response(
            items=[],
            total=0,
            page=page,
            page_size=page_size,
            filters={
                "property_type": property_type,
                "region": region,
                "municipality": municipality,
                "year": year,
                "search": search,
            },
            sort=sort,
            order=order,
        )
        await cache_set(request, cache_key, result)
        return result

    frame = _apply_market_filters(
        df,
        property_type=property_type,
        region=region,
        municipality=municipality,
        year=year,
        search=search,
    )
    municipality_groups = (
        [_municipality_stats(group) for _, group in frame.groupby("_municipality_slug")]
        if "_municipality_slug" in frame.columns
        else []
    )
    grouped = pd.DataFrame(municipality_groups)
    if grouped.empty:
        result = _build_explorer_response(
            items=[],
            total=0,
            page=page,
            page_size=page_size,
            filters={
                "property_type": _clean_query_value(property_type),
                "region": _clean_query_value(region),
                "municipality": _clean_query_value(municipality),
                "year": _clean_query_value(year),
                "search": _clean_query_value(search),
            },
            sort=sort,
            order=order,
        )
        await cache_set(request, cache_key, result)
        return result

    grouped = _sort_frame_for_explorer(grouped, sort=sort, order=order, default=["count", "municipality"])
    total = int(len(grouped))
    offset = (page - 1) * page_size
    items = grouped.iloc[offset : offset + page_size].replace({np.nan: None}).to_dict("records")

    result = _build_explorer_response(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        filters={
            "property_type": _clean_query_value(property_type),
            "region": _clean_query_value(region),
            "municipality": _clean_query_value(municipality),
            "year": _clean_query_value(year),
            "search": _clean_query_value(search),
        },
        sort=sort,
        order=order,
    )
    await cache_set(request, cache_key, result)
    return result


@router.get("/regions-explorer")
async def regions_explorer(
    request: Request,
    response: Response,
    property_type: str | None = None,
    region: str | None = None,
    municipality: str | None = None,
    year: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    sort: str = Query("count"),
    order: str = Query("desc"),
    _user: User = Depends(get_current_user),
):
    _set_stats_cache_headers(response)
    cache_key = _explorer_cache_key(
        "regions-explorer",
        property_type=property_type,
        region=region,
        municipality=municipality,
        year=year,
        search=search,
        page=page,
        page_size=page_size,
        sort=sort,
        order=order,
    )
    cached = await cache_get(request, cache_key)
    if cached is not None:
        return cached

    df = _prepare_market_df(property_type=property_type)
    if df is None or df.empty:
        result = _build_explorer_response(
            items=[],
            total=0,
            page=page,
            page_size=page_size,
            filters={
                "property_type": property_type,
                "region": region,
                "municipality": municipality,
                "year": year,
                "search": search,
            },
            sort=sort,
            order=order,
        )
        await cache_set(request, cache_key, result)
        return result

    frame = _apply_market_filters(
        df,
        property_type=property_type,
        region=region,
        municipality=municipality,
        year=year,
        search=search,
    )
    if frame.empty or "statistical_region" not in frame.columns:
        result = _build_explorer_response(
            items=[],
            total=0,
            page=page,
            page_size=page_size,
            filters={
                "property_type": _clean_query_value(property_type),
                "region": _clean_query_value(region),
                "municipality": _clean_query_value(municipality),
                "year": _clean_query_value(year),
                "search": _clean_query_value(search),
            },
            sort=sort,
            order=order,
        )
        await cache_set(request, cache_key, result)
        return result

    rows = []
    for region_name, group in frame.groupby("statistical_region"):
        rows.append(
            {
                "region": format_region_label(region_name) or str(region_name),
                "count": int(len(group)),
                "municipality_count": int(group["_municipality_slug"].nunique())
                if "_municipality_slug" in group.columns
                else 0,
                "avg_price": _round_or_none(group["price_eur"].mean()) if "price_eur" in group.columns else None,
                "median_price": _round_or_none(group["price_eur"].median()) if "price_eur" in group.columns else None,
                "avg_price_per_m2": _round_or_none(group["_price_per_m2"].dropna().mean()),
                "median_price_per_m2": _round_or_none(group["_price_per_m2"].dropna().median()),
                "latest_year": str(group["_year"].dropna().max())
                if "_year" in group.columns and group["_year"].notna().any()
                else None,
            }
        )

    grouped = pd.DataFrame(rows)
    grouped = _sort_frame_for_explorer(grouped, sort=sort, order=order, default=["count", "region"])
    total = int(len(grouped))
    offset = (page - 1) * page_size
    items = grouped.iloc[offset : offset + page_size].replace({np.nan: None}).to_dict("records")

    result = _build_explorer_response(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        filters={
            "property_type": _clean_query_value(property_type),
            "region": _clean_query_value(region),
            "municipality": _clean_query_value(municipality),
            "year": _clean_query_value(year),
            "search": _clean_query_value(search),
        },
        sort=sort,
        order=order,
    )
    await cache_set(request, cache_key, result)
    return result


@router.get("/municipality/{slug}")
async def municipality_detail(
    slug: str,
    request: Request,
    response: Response,
    property_type: str | None = None,
    year: str | None = None,
    _user: User = Depends(get_current_user),
):
    _set_stats_cache_headers(response)
    cache_key = (
        f"{_stats_cache_prefix('municipality')}:{municipality_slug(slug)}:{property_type or 'all'}:{year or 'all'}"
    )
    cached = await cache_get(request, cache_key)
    if cached is not None:
        return cached

    df = _prepare_market_df()
    if df is None or df.empty or "municipality" not in df.columns:
        raise HTTPException(status_code=404, detail="Municipality not found")

    viewer_df = _viewer_frame(df)
    municipality_source_df = _find_municipality_frame(viewer_df, slug)
    if municipality_source_df.empty:
        raise HTTPException(status_code=404, detail="Municipality not found")

    municipality_name = str(municipality_source_df["municipality"].iloc[0])
    municipality_slug_value = str(municipality_source_df["_municipality_slug"].iloc[0])
    region = (
        _mode_or_none(municipality_source_df["statistical_region"])
        if "statistical_region" in municipality_source_df.columns
        else None
    )
    municipality_df = _apply_market_filters(
        municipality_source_df,
        property_type=property_type,
        year=year,
        viewer_only=False,
    )
    filtered_viewer_df = _apply_market_filters(
        viewer_df,
        property_type=property_type,
        year=year,
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
        region_df = filtered_viewer_df[filtered_viewer_df["statistical_region"] == region]
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


@router.get("/municipality/{slug}/transactions")
async def municipality_transactions(
    slug: str,
    request: Request,
    response: Response,
    property_type: str | None = None,
    year: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    sort: str = Query("recent"),
    order: str = Query("desc"),
    _user: User = Depends(get_current_user),
):
    _set_stats_cache_headers(response)
    cache_key = _explorer_cache_key(
        f"municipality-transactions:{municipality_slug(slug)}",
        property_type=property_type,
        region=None,
        municipality=slug,
        year=year,
        search=search,
        page=page,
        page_size=page_size,
        sort=sort,
        order=order,
    )
    cached = await cache_get(request, cache_key)
    if cached is not None:
        return cached

    df = _prepare_market_df()
    if df is None or df.empty or "municipality" not in df.columns:
        raise HTTPException(status_code=404, detail="Municipality not found")

    frame = _viewer_frame(df)
    municipality_df = _find_municipality_frame(frame, slug)
    if municipality_df.empty:
        raise HTTPException(status_code=404, detail="Municipality not found")

    municipality_name = str(municipality_df["municipality"].iloc[0])
    municipality_df = _apply_market_filters(
        municipality_df,
        property_type=property_type,
        year=year,
        search=search,
    )
    municipality_df = _sort_frame_for_explorer(
        municipality_df,
        sort=None if sort == "recent" else sort,
        order=order,
        default=["_sale_date", "_year", "price_eur"],
    )

    total = int(len(municipality_df))
    offset = (page - 1) * page_size
    paged = municipality_df.iloc[offset : offset + page_size]
    items = [_serialize_price_row(row) for _, row in paged.iterrows()]

    response = _build_explorer_response(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        filters={
            "property_type": _clean_query_value(property_type),
            "region": None,
            "municipality": municipality_name,
            "year": _clean_query_value(year),
            "search": _clean_query_value(search),
        },
        sort=sort,
        order=order,
    )
    response["municipality"] = municipality_name
    response["slug"] = municipality_slug(municipality_name)
    await cache_set(request, cache_key, response)
    return response


@router.get("/naselja")
async def naselja(
    request: Request,
    response: Response = None,
    q: str | None = Query(None, min_length=1),
    municipality: str | None = Query(None),
    limit: int = Query(20, ge=5, le=50),
    _user: User = Depends(get_current_user),
):
    _set_stats_cache_headers(response)
    cache_key = (
        f"{_stats_cache_prefix('naselja')}:"
        f"{municipality_slug(municipality) if municipality else 'all'}:{_normalize_location_name(q)}:{limit}"
    )
    cached = await cache_get(request, cache_key)
    if cached is not None:
        return cached

    df = _prepare_market_df()
    if df is None or df.empty or "naselje" not in df.columns:
        return []

    frame = _viewer_frame(df)
    frame = frame[frame["_naselje_normalized"] != "unknown"]
    if municipality:
        muni_slug = municipality_slug(municipality)
        frame = frame[frame["_municipality_slug"] == muni_slug]

    if q:
        query = _normalize_location_name(q)
        frame = frame[frame["_naselje_normalized"].str.contains(query, na=False)]

    if frame.empty:
        return []

    group_columns = ["_naselje_normalized", "naselje", "municipality", "statistical_region"]
    rows = frame.groupby(group_columns, dropna=False).agg(sample_count=("naselje", "size")).reset_index()

    map_frame, _reason = _prepare_map_coordinates(frame)
    if map_frame.empty:
        rows["latitude"] = pd.NA
        rows["longitude"] = pd.NA
    else:
        coordinate_rows = (
            map_frame.groupby(group_columns, dropna=False)
            .agg(
                latitude=("_map_lat", "median"),
                longitude=("_map_lon", "median"),
            )
            .reset_index()
        )
        rows = rows.merge(coordinate_rows, on=group_columns, how="left")

    rows = rows.sort_values(["sample_count", "naselje"], ascending=[False, True]).head(limit)

    result = [
        {
            "naselje": str(row["naselje"]),
            "municipality": str(row["municipality"]),
            "region": str(row["statistical_region"]) if pd.notna(row["statistical_region"]) else None,
            "latitude": _round_or_none(row["latitude"], 6),
            "longitude": _round_or_none(row["longitude"], 6),
            "sample_count": int(row["sample_count"]),
        }
        for _, row in rows.iterrows()
    ]
    await cache_set(request, cache_key, result)
    return result


@router.get("/comparables")
async def comparables(
    request: Request,
    response: Response = None,
    municipality: str = Query(..., min_length=1),
    naselje: str | None = Query(None),
    property_type: str = Query(..., min_length=1),
    size_m2: float = Query(..., gt=1),
    year_built: int | None = Query(None, ge=1800, le=2030),
    price_eur: float | None = Query(None, gt=1),
    limit: int = Query(8, ge=3, le=20),
    _user: User = Depends(get_current_user),
):
    _set_stats_cache_headers(response)
    cache_key = (
        f"{_stats_cache_prefix('comparables')}:{municipality_slug(municipality)}:{_normalize_location_name(naselje)}:"
        f"{property_type}:{size_m2}:{year_built}:{price_eur}:{limit}"
    )
    cached = await cache_get(request, cache_key)
    if cached is not None:
        return cached

    full_df = _prepare_market_df()
    df = _prepare_market_df(property_type=property_type)
    target_slug = municipality_slug(municipality)
    target = {
        "municipality": municipality,
        "naselje": naselje,
        "slug": target_slug,
        "property_type": property_type,
        "size_m2": round(size_m2, 1),
        "year_built": year_built,
        "price_eur": _round_or_none(price_eur),
        "region": None,
    }

    if full_df is None or full_df.empty:
        return {"target": target, "summary": {"count": 0, "municipality_matched": False}, "items": []}

    target_df = _find_municipality_frame(full_df, municipality)
    municipality_matched = not target_df.empty
    region = (
        _mode_or_none(target_df["statistical_region"])
        if municipality_matched and "statistical_region" in target_df.columns
        else None
    )
    canonical_municipality = str(target_df["municipality"].iloc[0]) if municipality_matched else municipality
    target_naselje = naselje
    if naselje and "_naselje_normalized" in target_df.columns:
        naselje_key = _normalize_location_name(naselje)
        naselje_df = target_df[target_df["_naselje_normalized"] == naselje_key]
        if not naselje_df.empty:
            target_naselje = str(naselje_df["naselje"].iloc[0])
    target.update(
        {
            "municipality": canonical_municipality,
            "naselje": target_naselje,
            "slug": municipality_slug(canonical_municipality),
            "region": region,
        }
    )

    if df is None or df.empty:
        result = {"target": target, "summary": {"count": 0, "municipality_matched": municipality_matched}, "items": []}
        await cache_set(request, cache_key, result)
        return result

    candidates = _viewer_frame(df)
    candidates = candidates[candidates["_area"].notna() & (candidates["_area"] > 0)].copy()
    target_naselje_key = _normalize_location_name(target_naselje)
    if target_naselje and "_naselje_normalized" in candidates.columns:
        same_naselje = candidates[candidates["_naselje_normalized"] == target_naselje_key].copy()
        local_same_naselje = same_naselje[_municipality_match_mask(same_naselje, target["slug"])]
        regional_same_naselje = (
            same_naselje[same_naselje["statistical_region"] == region].copy()
            if region and "statistical_region" in same_naselje.columns
            else pd.DataFrame(columns=same_naselje.columns)
        )
        if len(local_same_naselje) >= limit:
            candidates = local_same_naselje
        elif len(regional_same_naselje) >= limit:
            candidates = regional_same_naselje
        elif not municipality_matched and len(same_naselje) >= limit:
            candidates = same_naselje
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

    candidates["location_bonus"] = 0.0
    if target_naselje and "_naselje_normalized" in candidates.columns:
        candidates["location_bonus"] += np.where(candidates["_naselje_normalized"] == target_naselje_key, 0.24, 0.0)
    municipality_match = _municipality_match_mask(candidates, target["slug"])
    candidates["location_bonus"] += np.where(municipality_match, 0.14, 0.0)
    if region:
        candidates["location_bonus"] += np.where(candidates["statistical_region"] == region, 0.06, 0.0)

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
            "naselje": target_naselje,
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
    request: Request,
    response: Response = None,
    region: str | None = None,
    _user: User = Depends(get_current_user),
):
    """Return {region: [municipality, ...]} from training data."""
    _set_stats_cache_headers(response)
    cache_key = f"{_stats_cache_prefix('municipalities-by-region')}:{region or 'all'}"
    cached = await cache_get(request, cache_key)
    if cached is not None:
        return cached

    prepared = _prepare_market_df()
    if prepared is None or prepared.empty:
        return [] if region else {}
    frame = _viewer_frame(prepared)
    if "municipality" not in frame.columns:
        result = [] if region else {}
        await cache_set(request, cache_key, result)
        return result

    if "statistical_region" not in frame.columns:
        frame["statistical_region"] = frame["municipality"].apply(
            lambda m: lookup_region(str(m)) if pd.notna(m) else "neznana"
        )

    mapping = frame[["municipality", "statistical_region"]].dropna().drop_duplicates()
    if region:
        filtered = mapping[mapping["statistical_region"].map(lambda value: labels_match(value, region))]
        result = [
            {"municipality": format_municipality_label(municipality) or municipality}
            for municipality in sorted(filtered["municipality"].unique().tolist())
        ]
        await cache_set(request, cache_key, result)
        return result

    result: dict[str, list[str]] = {}
    for region_name, group in mapping.groupby("statistical_region"):
        result[format_region_label(region_name) or str(region_name)] = sorted(
            (format_municipality_label(municipality) or municipality)
            for municipality in group["municipality"].unique().tolist()
        )
    await cache_set(request, cache_key, result)
    return result


def _map_overview_cache_key(
    *,
    property_type: str | None = None,
    statistical_region: str | None = None,
    year: str | None = None,
    municipality: str | None = None,
    price_band: str | None = None,
) -> str:
    municipality_key = municipality_slug(municipality) if municipality else "all"
    return (
        f"{_stats_cache_prefix('map-overview')}:"
        f"{property_type or 'all'}:{statistical_region or 'all'}:{year or 'all'}:{municipality_key}:{price_band or 'all'}"
    )


def _map_transactions_cache_key(
    *,
    property_type: str | None = None,
    statistical_region: str | None = None,
    year: str | None = None,
    municipality: str | None = None,
    price_band: str | None = None,
    limit: int | None = None,
) -> str:
    municipality_key = municipality_slug(municipality) if municipality else "all"
    return (
        f"{_stats_cache_prefix('map-transactions')}:"
        f"{property_type or 'all'}:{statistical_region or 'all'}:{year or 'all'}:{municipality_key}:{price_band or 'all'}:{limit}"
    )


def _default_market_year(df: pd.DataFrame) -> str | None:
    if "_year" not in df.columns:
        return None

    years = pd.to_numeric(df["_year"], errors="coerce").dropna().astype(int)
    if years.empty:
        return None

    current_year = int(pd.Timestamp.now("UTC").year)
    completed_years = years[years < current_year]
    target_year = int(completed_years.max()) if not completed_years.empty else int(years.max())
    return str(target_year)


def _filtered_map_frame(
    df: pd.DataFrame,
    *,
    property_type: str | None = None,
    statistical_region: str | None = None,
    year: str | None = None,
    municipality: str | None = None,
) -> pd.DataFrame:
    return _apply_market_filters(
        df,
        property_type=property_type,
        region=statistical_region,
        municipality=municipality,
        year=year,
    )


def _build_map_overview_payload(
    df: pd.DataFrame | None,
    *,
    property_type: str | None = None,
    statistical_region: str | None = None,
    year: str | None = None,
    municipality: str | None = None,
    price_band: str | None = None,
) -> dict:
    if df is None or df.empty:
        return {"municipalities": [], "count": 0, "meta": {"reason": "no_train_dataset"}}

    frame = _filtered_map_frame(
        df,
        property_type=property_type,
        statistical_region=statistical_region,
        year=year,
        municipality=municipality,
    )
    if frame.empty:
        return {"municipalities": [], "count": 0, "meta": {"reason": "no_matches"}}

    map_df, reason = _prepare_map_coordinates(frame)
    if map_df.empty:
        return {"municipalities": [], "count": 0, "meta": {"reason": reason or "no_coordinates"}}

    municipalities = []
    group_key = "_municipality_slug" if "_municipality_slug" in map_df.columns else "municipality"
    for _, group in map_df.groupby(group_key):
        avg_price_per_m2 = _round_or_none(group["_price_per_m2"].dropna().mean())
        municipalities.append(
            {
                "municipality": (
                    format_municipality_label(group["municipality"].iloc[0])
                    if "municipality" in group.columns
                    else "unknown"
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
                "avg_price_per_m2": avg_price_per_m2,
                "price_band": None,
            }
        )

    legend = _build_price_band_meta(pd.Series([item["avg_price_per_m2"] for item in municipalities], dtype=float))
    for item in municipalities:
        item["price_band"] = _price_band_key(item.get("avg_price_per_m2"), legend["thresholds"]) if legend else None

    if price_band:
        municipalities = [item for item in municipalities if item.get("price_band") == str(price_band).casefold()]
        if not municipalities:
            return {
                "municipalities": [],
                "count": 0,
                "meta": {"reason": "no_matches", "legend": legend, "price_band": price_band},
            }

    municipalities.sort(key=lambda item: item["count"], reverse=True)
    return {
        "municipalities": municipalities,
        "count": len(municipalities),
        "meta": {
            "reason": None,
            "legend": legend,
            "price_band": price_band,
            "filtered_total": len(municipalities),
        },
    }


def _build_map_transactions_payload(
    df: pd.DataFrame | None,
    *,
    property_type: str | None = None,
    statistical_region: str | None = None,
    year: str | None = None,
    municipality: str | None = None,
    price_band: str | None = None,
    limit: int | None = None,
) -> dict:
    if df is None or df.empty:
        return {"transactions": [], "count": 0, "meta": {"reason": "no_train_dataset"}}

    frame = _filtered_map_frame(
        df,
        property_type=property_type,
        statistical_region=statistical_region,
        year=year,
        municipality=municipality,
    )
    if frame.empty:
        return {"transactions": [], "count": 0, "meta": {"reason": "no_matches"}}

    map_df, reason = _prepare_map_coordinates(frame)
    if map_df.empty:
        return {"transactions": [], "count": 0, "meta": {"reason": reason or "no_coordinates"}}

    legend = _build_price_band_meta(map_df["_price_per_m2"])
    if legend:
        map_df["_price_band"] = map_df["_price_per_m2"].map(lambda value: _price_band_key(value, legend["thresholds"]))
    else:
        map_df["_price_band"] = None

    filtered_total = int(len(map_df))
    if price_band:
        map_df = map_df[map_df["_price_band"] == str(price_band).casefold()]
        if map_df.empty:
            return {
                "transactions": [],
                "count": 0,
                "meta": {"reason": "no_matches", "legend": legend, "price_band": price_band},
            }

    filtered_after_band = int(len(map_df))
    truncated = False
    if isinstance(limit, int) and len(map_df) > limit:
        map_df = map_df.sample(n=limit, random_state=42)
        truncated = True

    map_df = map_df.copy()
    map_df["_area"] = _effective_area(map_df)

    transactions = []
    for _, row in map_df.iterrows():
        item = _serialize_price_row(row)
        item["price_band"] = row.get("_price_band")
        transactions.append(item)

    return {
        "transactions": transactions,
        "count": len(transactions),
        "meta": {
            "reason": None,
            "legend": legend,
            "price_band": price_band,
            "filtered_total": filtered_total,
            "band_total": filtered_after_band,
            "returned_total": len(transactions),
            "truncated": truncated,
        },
    }


def build_common_stats_cache_entries() -> list[tuple[str, object, int]]:
    df = _prepare_market_df()
    if df is None or df.empty:
        return []

    default_year = _default_market_year(df)
    years_to_warm = [None]
    if default_year:
        years_to_warm.append(default_year)

    entries: list[tuple[str, object, int]] = []
    seen: set[str] = set()

    def add_entry(cache_key: str, payload: object):
        if cache_key in seen:
            return
        entries.append((cache_key, payload, STATS_CACHE_TTL))
        seen.add(cache_key)

    default_filters = {
        "property_type": None,
        "region": None,
        "municipality": None,
        "year": None,
        "search": None,
    }

    def build_default_transactions_payload(*, page_size: int, sort: str, order: str) -> dict:
        frame = _apply_market_filters(df)
        frame = _sort_frame_for_explorer(
            frame,
            sort=None if sort == "recent" else sort,
            order=order,
            default=["_sale_date", "_year", "price_eur"],
        )
        items = [_serialize_price_row(row) for _, row in frame.iloc[:page_size].iterrows()]
        return _build_explorer_response(
            items=items,
            total=int(len(frame)),
            page=1,
            page_size=page_size,
            filters=default_filters,
            sort=sort,
            order=order,
        )

    def build_default_municipalities_payload(*, page_size: int, sort: str, order: str) -> dict:
        frame = _apply_market_filters(df)
        municipality_groups = (
            [_municipality_stats(group) for _, group in frame.groupby("_municipality_slug")]
            if "_municipality_slug" in frame.columns
            else []
        )
        grouped = pd.DataFrame(municipality_groups)
        if grouped.empty:
            return _build_explorer_response(
                items=[],
                total=0,
                page=1,
                page_size=page_size,
                filters=default_filters,
                sort=sort,
                order=order,
            )

        grouped = _sort_frame_for_explorer(grouped, sort=sort, order=order, default=["count", "municipality"])
        items = grouped.iloc[:page_size].replace({np.nan: None}).to_dict("records")
        return _build_explorer_response(
            items=items,
            total=int(len(grouped)),
            page=1,
            page_size=page_size,
            filters=default_filters,
            sort=sort,
            order=order,
        )

    def build_default_regions_payload(*, page_size: int, sort: str, order: str) -> dict:
        frame = _apply_market_filters(df)
        if frame.empty or "statistical_region" not in frame.columns:
            return _build_explorer_response(
                items=[],
                total=0,
                page=1,
                page_size=page_size,
                filters=default_filters,
                sort=sort,
                order=order,
            )

        rows = []
        for region_name, group in frame.groupby("statistical_region"):
            rows.append(
                {
                    "region": format_region_label(region_name) or str(region_name),
                    "count": int(len(group)),
                    "municipality_count": int(group["_municipality_slug"].nunique())
                    if "_municipality_slug" in group.columns
                    else 0,
                    "avg_price": _round_or_none(group["price_eur"].mean()) if "price_eur" in group.columns else None,
                    "median_price": _round_or_none(group["price_eur"].median())
                    if "price_eur" in group.columns
                    else None,
                    "avg_price_per_m2": _round_or_none(group["_price_per_m2"].dropna().mean()),
                    "median_price_per_m2": _round_or_none(group["_price_per_m2"].dropna().median()),
                    "latest_year": str(group["_year"].dropna().max())
                    if "_year" in group.columns and group["_year"].notna().any()
                    else None,
                }
            )

        grouped = pd.DataFrame(rows)
        grouped = _sort_frame_for_explorer(grouped, sort=sort, order=order, default=["count", "region"])
        items = grouped.iloc[:page_size].replace({np.nan: None}).to_dict("records")
        return _build_explorer_response(
            items=items,
            total=int(len(grouped)),
            page=1,
            page_size=page_size,
            filters=default_filters,
            sort=sort,
            order=order,
        )

    for year in years_to_warm:
        overview_key = _map_overview_cache_key(year=year)
        add_entry(overview_key, _build_map_overview_payload(df, year=year))

        transactions_key = _map_transactions_cache_key(year=year, limit=None)
        add_entry(transactions_key, _build_map_transactions_payload(df, year=year, limit=None))

    add_entry(
        f"{_stats_cache_prefix('market-home')}:all:all:all:all",
        _build_market_home_payload(df, property_type=None, region=None, municipality=None, year=None),
    )
    add_entry(f"{_stats_cache_prefix('trend')}:all:all:all", _build_trend_payload(_apply_market_filters(df)))
    add_entry(
        f"{_stats_cache_prefix('overview')}:all:all:all:all",
        _build_overview_payload(_apply_market_filters(df)),
    )
    add_entry(
        f"{_stats_cache_prefix('regions')}:all:all:all:all",
        _build_regions_stats_payload(_apply_market_filters(df)),
    )
    add_entry(
        f"{_stats_cache_prefix('price-distribution')}:20:all:all:all:all",
        _build_price_distribution_payload(_apply_market_filters(df), bins=20),
    )
    add_entry(
        _explorer_cache_key(
            "transactions",
            property_type=None,
            region=None,
            municipality=None,
            year=None,
            search=None,
            page=1,
            page_size=6,
            sort="recent",
            order="desc",
        ),
        build_default_transactions_payload(page_size=6, sort="recent", order="desc"),
    )
    add_entry(
        _explorer_cache_key(
            "municipalities",
            property_type=None,
            region=None,
            municipality=None,
            year=None,
            search=None,
            page=1,
            page_size=8,
            sort="count",
            order="desc",
        ),
        build_default_municipalities_payload(page_size=8, sort="count", order="desc"),
    )
    add_entry(
        _explorer_cache_key(
            "municipalities",
            property_type=None,
            region=None,
            municipality=None,
            year=None,
            search=None,
            page=1,
            page_size=24,
            sort="count",
            order="desc",
        ),
        build_default_municipalities_payload(page_size=24, sort="count", order="desc"),
    )
    add_entry(
        _explorer_cache_key(
            "regions-explorer",
            property_type=None,
            region=None,
            municipality=None,
            year=None,
            search=None,
            page=1,
            page_size=8,
            sort="count",
            order="desc",
        ),
        build_default_regions_payload(page_size=8, sort="count", order="desc"),
    )
    add_entry(
        _explorer_cache_key(
            "regions-explorer",
            property_type=None,
            region=None,
            municipality=None,
            year=None,
            search=None,
            page=1,
            page_size=12,
            sort="median_price_per_m2",
            order="desc",
        ),
        build_default_regions_payload(page_size=12, sort="median_price_per_m2", order="desc"),
    )

    return entries


@router.get("/map-overview")
async def map_overview(
    request: Request,
    response: Response,
    property_type: str | None = None,
    statistical_region: str | None = None,
    year: str | None = None,
    municipality: str | None = None,
    price_band: str | None = None,
    _user: User = Depends(get_current_user),
):
    """Return municipality markers for the overview map without relying on model artifacts."""
    _set_stats_cache_headers(response)
    cache_key = _map_overview_cache_key(
        property_type=property_type,
        statistical_region=statistical_region,
        year=year,
        municipality=municipality,
        price_band=price_band,
    )
    cached = await cache_get(request, cache_key)
    if cached is not None:
        return cached

    result = _build_map_overview_payload(
        _prepare_market_df(),
        property_type=property_type,
        statistical_region=statistical_region,
        year=year,
        municipality=municipality,
        price_band=price_band,
    )
    await cache_set(request, cache_key, result)
    return result


@router.get("/map-transactions")
async def map_transactions(
    request: Request = None,
    response: Response = None,
    property_type: str | None = None,
    statistical_region: str | None = None,
    year: str | None = None,
    municipality: str | None = None,
    price_band: str | None = None,
    limit: int | None = Query(None, ge=100, le=100000),
    _user: User = Depends(get_current_user),
):
    """Return transaction points for map visualization (WGS84 coords)."""
    _set_stats_cache_headers(response)
    if not isinstance(limit, int):
        limit = None
    cache_key = _map_transactions_cache_key(
        property_type=property_type,
        statistical_region=statistical_region,
        year=year,
        municipality=municipality,
        price_band=price_band,
        limit=limit,
    )
    cached = await cache_get(request, cache_key) if request is not None else None
    if cached is not None:
        return cached

    result = _build_map_transactions_payload(
        _prepare_market_df(),
        property_type=property_type,
        statistical_region=statistical_region,
        year=year,
        municipality=municipality,
        price_band=price_band,
        limit=limit,
    )
    if request is not None:
        await cache_set(request, cache_key, result)
    return result
