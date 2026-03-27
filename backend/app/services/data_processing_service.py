"""Data processing service — ETN CSV parsing, feature extraction, training data preparation."""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
import re
import shutil
import sqlite3
import struct as _struct
import tempfile
import unicodedata
import uuid
import zipfile
from functools import lru_cache
from typing import Any, Callable

import numpy as np
import pandas as pd

from app.services.regions_service import FALLBACK_REGIONS, lookup_region, lookup_region_by_code, normalize
from app.utils.municipality import normalize_municipality_name
from app.utils.slovenian_labels import format_municipality_label

logger = logging.getLogger(__name__)

# Property type mapping from VRSTA_DELA_STAVBE codes
_PROPERTY_TYPE_MAP = {
    1: "hisa",
    2: "stanovanje",
    3: "stanovanje",
    4: "poslovni_prostor",
    5: "poslovni_prostor",
    6: "industrijski",
    7: "industrijski",
    8: "industrijski",
    9: "poslovni_prostor",
    10: "turisticni",
    11: "gostinstvo",
    12: "gostinstvo",
    13: "klet_shramba",
    14: "klet_shramba",
    15: "garaza",
    16: "garaza",
    17: "kmetijsko",
    18: "kmetijsko",
    19: "kmetijsko",
    20: "kmetijsko",
    21: "industrijski",
    22: "poslovni_prostor",
    23: "poslovni_prostor",
    24: "poslovni_prostor",
    25: "poslovni_prostor",
    26: "poslovni_prostor",
    27: "kmetijsko",
    28: "kmetijsko",
    29: "kmetijsko",
    30: "poslovni_prostor",
    31: "poslovni_prostor",
    32: "poslovni_prostor",
    33: "klet_shramba",
    34: "klet_shramba",
    35: "ostalo",
    36: "ostalo",
    37: "ostalo",
    38: "ostalo",
    39: "ostalo",
    40: "stanovanje",
    41: "stanovanje",
    42: "hisa",
    43: "hisa",
    44: "hisa",
    45: "hisa",
    46: "hisa",
    47: "stanovanje",
    48: "stanovanje",
    49: "stanovanje",
    50: "poslovni_prostor",
    51: "industrijski",
    52: "industrijski",
    53: "poslovni_prostor",
    54: "turisticni",
    55: "turisticni",
    56: "gostinstvo",
    57: "klet_shramba",
    58: "garaza",
    59: "garaza",
    60: "hisa",
    61: "kmetijsko",
    62: "kmetijsko",
}

_CC_SI_PREFIX_MAP = {
    "1110": "hisa",
    "1121": "hisa",
    "1122": "stanovanje",
    "1130": "stanovanje",
    "1200": "ostalo",
    "1211": "gostinstvo",
    "1212": "turisticni",
    "1220": "poslovni_prostor",
    "1230": "poslovni_prostor",
    "1241": "poslovni_prostor",
    "1242": "garaza",
    "1251": "industrijski",
    "1252": "industrijski",
    "1261": "poslovni_prostor",
    "1262": "poslovni_prostor",
    "1263": "poslovni_prostor",
    "1264": "poslovni_prostor",
    "1265": "poslovni_prostor",
    "1271": "kmetijsko",
    "1272": "poslovni_prostor",
    "1274": "klet_shramba",
    "1280": "ostalo",
    "1290": "ostalo",
}

EXCLUDED_PROPERTY_TYPES = {"ostalo", "klet_shramba"}

_LATEST_UPLOAD_PATTERNS = {
    "rn": "_RN_SLO_NASLOVI_register_naslovov_",
    "ev_stavba": "_EV_SLO_EVIDENCA_VREDNOTENJA_stavba_",
    "ev_del_stavbe": "_EV_SLO_EVIDENCA_VREDNOTENJA_del_stavbe_",
    "ev_del_stavbe_enota": "_EV_SLO_EVIDENCA_VREDNOTENJA_del_stavbe_enota_",
    "ev_parcela": "_EV_SLO_EVIDENCA_VREDNOTENJA_parcela_",
    "ev_parc_enota": "_EV_SLO_EVIDENCA_VREDNOTENJA_parc_enota_",
    "kn_kat_obcine": "_KN_SLO_KAT_OBCINE_",
    "kn_ggo": "_KN_SLO_GGO_",
    "gji_vodovod": "_KGI_SLO_GJI_VODOVOD_linije_",
    "gji_kanalizacija": "_KGI_SLO_GJI_KANALIZACIJA_linije_",
    "gji_elektrika": "_KGI_SLO_GJI_ELEKTRICNA_ENERGIJA_linije_",
    "gji_plin": "_KGI_SLO_GJI_ZEM_PLIN_linije_",
    "gji_ceste": "_KGI_SLO_GJI_CESTE_linije_",
    "gji_toplota": "_KGI_SLO_GJI_TOPLOTNA_ENERGIJA_linije_",
    "emv": "_emv_vredn_cone_",
}

_EMV_TARGET_CRS = "EPSG:3794"
_KN_KO_LAYER = "KN_SLO_KAT_OBCINE_KATASTRSKE_OBCINE_poligon"
_KN_GGO_LAYER = "KN_SLO_GGO_GOZDNO_GOSP_OBM_poligon"
_GJI_NEARBY_DISTANCE_M = 100.0
_SPATIAL_TILE_SIZE_M = 20_000.0
_SPATIAL_BATCH_SIZE = 5_000
_SPATIAL_BBOX_PADDING_M = 250.0
_EMV_LAYER_CANDIDATES_BY_PROPERTY_TYPE: dict[str, list[str]] = {
    "stanovanje": ["emv_vredn_cone_STA"],
    "hisa": ["emv_vredn_cone_HIS"],
    "garaza": ["emv_vredn_cone_GAR"],
    "industrijski": ["emv_vredn_cone_IND", "emv_vredn_cone_INP"],
    "poslovni_prostor": ["emv_vredn_cone_PPP", "emv_vredn_cone_PPL"],
    "turisticni": ["emv_vredn_cone_TUR"],
    "gostinstvo": ["emv_vredn_cone_TUR", "emv_vredn_cone_PPP"],
    "kmetijsko": ["emv_vredn_cone_KME", "emv_vredn_cone_GOZ", "emv_vredn_cone_KDS", "emv_vredn_cone_SDP"],
    "parcela": [
        "emv_vredn_cone_STZ",
        "emv_vredn_cone_PNB",
        "emv_vredn_cone_PNE",
        "emv_vredn_cone_PNP",
        "emv_vredn_cone_KME",
        "emv_vredn_cone_GOZ",
    ],
}

_EMV_LAYER_CANDIDATES_BY_LAND_TYPE: dict[str, list[str]] = {
    "stavbno": ["emv_vredn_cone_STZ"],
    "kmetijsko": ["emv_vredn_cone_KME"],
    "gozdno": ["emv_vredn_cone_GOZ"],
}

DEFAULT_ENRICHMENT_OPTIONS: dict[str, Any] = {
    "enable_rn": True,
    "enable_ev": True,
    "enable_kn": True,
    "enable_gji": True,
    "enable_emv": True,
    "variant_label": "default",
}


def normalize_text(value: Any) -> str:
    if pd.isna(value):
        return "unknown"
    text = str(value).strip()
    if not text:
        return "unknown"
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.split()).lower() or "unknown"


def clean_display_text(value: Any) -> str:
    """Normalize whitespace while preserving Slovenian casing and diacritics."""
    if pd.isna(value):
        return "unknown"

    text = " ".join(str(value).strip().split())
    return text or "unknown"


def _classify_land_type_for_emv(raw_value: Any) -> str | None:
    normalized = normalize_text(raw_value)
    if normalized == "unknown":
        return None

    compact = normalized.replace(" ", "")
    if normalized in {"7", "stavbno"} or "stavbn" in compact or "zazid" in compact:
        return "stavbno"
    if normalized in {"6", "gozdno", "gozd"} or "gozd" in compact:
        return "gozdno"
    if normalized in {"1", "2", "3", "4", "5", "kmetijsko"}:
        return "kmetijsko"
    if any(token in compact for token in ["kmetij", "njiv", "trav", "pasnik", "pasnik", "vinograd", "sadovnjak", "hmelj"]):
        return "kmetijsko"
    return None


def _emv_layers_for_row(property_type: Any, land_type: Any = None) -> list[str]:
    property_type_key = normalize_text(property_type)
    if property_type_key == "parcela":
        land_group = _classify_land_type_for_emv(land_type)
        if land_group is not None:
            return _EMV_LAYER_CANDIDATES_BY_LAND_TYPE[land_group]
    return _EMV_LAYER_CANDIDATES_BY_PROPERTY_TYPE.get(property_type_key, [])


def resolve_enrichment_options(options: dict[str, Any] | None = None) -> dict[str, Any]:
    resolved = dict(DEFAULT_ENRICHMENT_OPTIONS)
    if options:
        for key in ["enable_rn", "enable_ev", "enable_kn", "enable_gji", "enable_emv"]:
            if key in options:
                resolved[key] = bool(options[key])
        variant_label = str(options.get("variant_label") or "").strip()
        if variant_label:
            resolved["variant_label"] = variant_label

    if resolved["variant_label"] == "default" and (
        not resolved["enable_rn"]
        or not resolved["enable_ev"]
        or not resolved["enable_kn"]
        or not resolved["enable_gji"]
        or not resolved["enable_emv"]
    ):
        enabled_tokens = []
        if resolved["enable_rn"]:
            enabled_tokens.append("rn")
        if resolved["enable_ev"]:
            enabled_tokens.append("ev")
        if resolved["enable_kn"]:
            enabled_tokens.append("kn")
        if resolved["enable_gji"]:
            enabled_tokens.append("gji")
        if resolved["enable_emv"]:
            enabled_tokens.append("emv")
        resolved["variant_label"] = "+".join(enabled_tokens) if enabled_tokens else "etn_only"

    return resolved


def _parse_fractional_numeric_series(series: pd.Series) -> pd.Series:
    def _parse_value(value: Any) -> float:
        if pd.isna(value):
            return np.nan

        if isinstance(value, (int, float, np.integer, np.floating)):
            return float(value)

        text = str(value).strip()
        if not text:
            return np.nan

        text = text.replace(",", ".")
        if "/" in text:
            numerator_text, denominator_text = (part.strip() for part in text.split("/", 1))
            try:
                numerator = float(numerator_text)
                denominator = float(denominator_text)
            except ValueError:
                return np.nan
            if denominator == 0:
                return np.nan
            return numerator / denominator

        try:
            return float(text)
        except ValueError:
            return np.nan

    return series.apply(_parse_value).astype("float64")


def _first_numeric_series(df: pd.DataFrame, candidates: list[str]) -> pd.Series:
    for candidate in candidates:
        if candidate in df.columns:
            return _parse_fractional_numeric_series(df[candidate])
    return pd.Series(np.nan, index=df.index, dtype="float64")


def _normalize_gradbena_faza(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    return values.where(values.isin([1, 2, 3, 4, 5, 6]), np.nan)


def group_property_type(raw_value: Any) -> str:
    if pd.isna(raw_value):
        return "ostalo"
    text = str(raw_value).strip()
    if not text:
        return "ostalo"
    try:
        code = int(text.split("-")[0].split(" ")[0].strip())
    except (ValueError, IndexError):
        try:
            code = int(text)
        except ValueError:
            return "ostalo"
    result = _PROPERTY_TYPE_MAP.get(code)
    if result is not None:
        return result
    if code > 100:
        return _CC_SI_PREFIX_MAP.get(str(code)[:4], "ostalo")
    return "ostalo"


def compute_file_sha256(file_path: str) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def get_available_disk_bytes(path: str) -> int:
    return shutil.disk_usage(path).free


def ensure_directory_headroom(path: str, required_bytes: int, reserve_bytes: int = 0) -> int:
    free_bytes = get_available_disk_bytes(path)
    if free_bytes - required_bytes < reserve_bytes:
        raise OSError(
            f"Insufficient disk space: requires {required_bytes} bytes plus {reserve_bytes} bytes reserve, "
            f"but only {free_bytes} bytes are free"
        )
    return free_bytes


def estimate_zip_uncompressed_size(zip_path: str) -> int:
    with zipfile.ZipFile(zip_path, "r") as archive:
        return sum(info.file_size for info in archive.infolist() if not info.is_dir())


def read_csv_flexible(csv_path: str, **read_kwargs: Any) -> pd.DataFrame:
    for encoding in ["utf-8", "cp1250", "latin1"]:
        for sep in [",", ";", "\t"]:
            try:
                return pd.read_csv(csv_path, encoding=encoding, sep=sep, low_memory=False, **read_kwargs)
            except Exception:
                try:
                    python_kwargs = dict(read_kwargs)
                    python_kwargs.setdefault("on_bad_lines", "skip")
                    return pd.read_csv(
                        csv_path,
                        encoding=encoding,
                        sep=sep,
                        engine="python",
                        low_memory=False,
                        **python_kwargs,
                    )
                except Exception:
                    continue
    raise ValueError(f"Cannot read CSV: {csv_path}")


def _normalize_numeric_key(value: Any) -> str | None:
    if pd.isna(value):
        return None

    text = str(value).strip()
    if not text:
        return None

    try:
        numeric = float(text.replace(",", "."))
    except ValueError:
        return None

    if np.isnan(numeric):
        return None
    return str(int(numeric))


def _normalize_numeric_key_series(series: pd.Series) -> pd.Series:
    return series.apply(_normalize_numeric_key)


def _normalize_text_key(value: Any) -> str | None:
    if pd.isna(value):
        return None
    text = normalize_text(value)
    return None if text == "unknown" else text


def _normalize_text_key_series(series: pd.Series) -> pd.Series:
    return series.apply(_normalize_text_key)


def _normalize_house_number_key(value: Any) -> str | None:
    text = _normalize_text_key(value)
    if text is None:
        return None
    if re.fullmatch(r"\d+\.0+", text):
        return text.split(".", 1)[0]
    return text


def _normalize_house_number_key_series(series: pd.Series) -> pd.Series:
    return series.apply(_normalize_house_number_key)


def _normalize_parcel_key(value: Any) -> str | None:
    if pd.isna(value):
        return None
    text = "".join(str(value).strip().split())
    if not text:
        return None
    if text.endswith(".0"):
        text = text[:-2]
    return text or None


def _normalize_parcel_key_series(series: pd.Series) -> pd.Series:
    return series.apply(_normalize_parcel_key)


def _compose_join_key(*parts: Any, allow_empty_trailing: bool = True) -> str | None:
    normalized_parts: list[str] = []
    for part in parts:
        if part is None or (isinstance(part, float) and np.isnan(part)):
            normalized_parts.append("")
        else:
            text = str(part).strip()
            normalized_parts.append(text)
    # At least the first part must be non-empty
    if not normalized_parts or not normalized_parts[0]:
        return None
    # Strip empty trailing parts (e.g. dodatek_hs is often missing)
    if allow_empty_trailing:
        while len(normalized_parts) > 1 and not normalized_parts[-1]:
            normalized_parts.pop()
    else:
        # All parts must be non-empty
        if any(not p for p in normalized_parts):
            return None
    return "|".join(normalized_parts)


def _find_latest_uploaded_file(upload_dir: str, marker: str) -> str | None:
    candidates: list[str] = []
    with contextlib.suppress(FileNotFoundError):
        for name in os.listdir(upload_dir):
            if marker not in name or name.endswith(".preview.json"):
                continue
            full_path = os.path.join(upload_dir, name)
            if os.path.isfile(full_path):
                candidates.append(full_path)

    if not candidates:
        return None
    return max(candidates, key=os.path.getmtime)


def discover_gurs_enrichment_sources(upload_dir: str) -> dict[str, str]:
    discovered: dict[str, str] = {}
    for source_name, marker in _LATEST_UPLOAD_PATTERNS.items():
        path = _find_latest_uploaded_file(upload_dir, marker)
        if (
            source_name == "ev_del_stavbe"
            and path is not None
            and "_EV_SLO_EVIDENCA_VREDNOTENJA_del_stavbe_enota_" in os.path.basename(path)
        ):
            candidates: list[str] = []
            with contextlib.suppress(FileNotFoundError):
                for name in os.listdir(upload_dir):
                    if marker not in name or name.endswith(".preview.json"):
                        continue
                    if "_EV_SLO_EVIDENCA_VREDNOTENJA_del_stavbe_enota_" in name:
                        continue
                    full_path = os.path.join(upload_dir, name)
                    if os.path.isfile(full_path):
                        candidates.append(full_path)
            path = max(candidates, key=os.path.getmtime) if candidates else None
        if path:
            discovered[source_name] = path
    return discovered


@lru_cache(maxsize=8)
def _load_rn_lookup_cached(rn_csv_path: str, mtime: float) -> pd.DataFrame:
    usecols = [
        "OBCINA_SIFRA",
        "OBCINA_NAZIV",
        "NASELJE_NAZIV",
        "ULICA_NAZIV",
        "HS_STEVILKA",
        "HS_DODATEK",
        "E",
        "N",
        "EID_NASLOV",
        "EID_NASELJE",
        "EID_ULICA",
        "EID_STAVBA",
        "EID_STATISTICNA_REGIJA",
    ]
    rn_df = read_csv_flexible(rn_csv_path, usecols=lambda col: col in usecols)
    rn_df["obcina_sifra_key"] = _normalize_numeric_key_series(rn_df["OBCINA_SIFRA"])
    rn_df["obcina_naziv_key"] = _normalize_text_key_series(rn_df["OBCINA_NAZIV"])
    rn_df["naselje_key"] = _normalize_text_key_series(rn_df["NASELJE_NAZIV"])
    rn_df["ulica_key"] = _normalize_text_key_series(rn_df["ULICA_NAZIV"])
    rn_df["hs_stevilka_key"] = _normalize_house_number_key_series(rn_df["HS_STEVILKA"])
    rn_df["hs_dodatek_key"] = _normalize_text_key_series(rn_df["HS_DODATEK"])
    rn_df["address_join_key"] = [
        _compose_join_key(obcina, naselje, ulica or "", hs, dodatek or "")
        for obcina, naselje, ulica, hs, dodatek in zip(
            rn_df["obcina_sifra_key"],
            rn_df["naselje_key"],
            rn_df["ulica_key"],
            rn_df["hs_stevilka_key"],
            rn_df["hs_dodatek_key"],
            strict=False,
        )
    ]
    rn_df["address_join_key_by_name"] = [
        _compose_join_key(obcina, naselje, ulica or "", hs, dodatek or "")
        for obcina, naselje, ulica, hs, dodatek in zip(
            rn_df["obcina_naziv_key"],
            rn_df["naselje_key"],
            rn_df["ulica_key"],
            rn_df["hs_stevilka_key"],
            rn_df["hs_dodatek_key"],
            strict=False,
        )
    ]
    rn_df = rn_df.drop_duplicates(subset=["address_join_key"], keep="first")
    return rn_df


def _load_rn_lookup(rn_csv_path: str) -> pd.DataFrame:
    return _load_rn_lookup_cached(rn_csv_path, os.path.getmtime(rn_csv_path)).copy()


@lru_cache(maxsize=4)
def _load_ev_building_lookup_cached(stavba_csv_path: str, del_csv_path: str, stavba_mtime: float, del_mtime: float) -> pd.DataFrame:
    stavba_cols = [
        "EID_STAVBA",
        "KO_SIFKO",
        "STEV_ST",
        "ST_ETAZ",
        "LETO_IZG_STA",
        "LETO_OBN_STREHE",
        "LETO_OBN_FASADE",
        "ID_KONSTRUKCIJA",
        "IMA_VODOVOD_DN",
        "IMA_ELEKTRIKO_DN",
        "IMA_KANALIZACIJO_DN",
        "IMA_PLIN_DN",
        "ID_TIP_STAVBE",
        "ST_STANOVANJ",
        "ST_POSLOVNIH_PROSTOROV",
        "POV_STAVBE",
        "RPE_OBCINE_SIFRA",
    ]
    del_cols = [
        "EID_DEL_STAVBE",
        "EID_STAVBA",
        "STEV_DST",
        "POVRSINA",
        "UPOR_POV",
        "LETO_OBN_OKEN",
        "LETO_OBN_INST",
        "ST_NADSTROPJA",
        "ID_LEGA",
        "IMA_DVIGALO_DN",
        "VISINA_ETAZE",
        "ID_DR_DST",
        "ZPS_DST",
    ]

    stavba_df = read_csv_flexible(stavba_csv_path, usecols=lambda col: col in stavba_cols)
    del_df = read_csv_flexible(del_csv_path, usecols=lambda col: col in del_cols)

    stavba_df["EID_STAVBA_KEY"] = _normalize_numeric_key_series(stavba_df["EID_STAVBA"])
    del_df["EID_DEL_STAVBE_KEY"] = _normalize_numeric_key_series(del_df["EID_DEL_STAVBE"])
    stavba_df["ko_key"] = _normalize_numeric_key_series(stavba_df["KO_SIFKO"])
    stavba_df["stavba_key"] = _normalize_numeric_key_series(stavba_df["STEV_ST"])
    del_df["EID_STAVBA_KEY"] = _normalize_numeric_key_series(del_df["EID_STAVBA"])
    del_df["del_key"] = _normalize_numeric_key_series(del_df["STEV_DST"])

    combined = del_df.merge(
        stavba_df,
        on="EID_STAVBA_KEY",
        how="left",
        suffixes=("_DEL", "_ST"),
    )
    combined["building_part_join_key"] = [
        _compose_join_key(ko, stavba, del_stavbe, allow_empty_trailing=False)
        for ko, stavba, del_stavbe in zip(
            combined["ko_key"],
            combined["stavba_key"],
            combined["del_key"],
            strict=False,
        )
    ]
    combined = combined.dropna(subset=["building_part_join_key"])
    combined = combined.drop_duplicates(subset=["building_part_join_key"], keep="first")
    return combined


def _load_ev_building_lookup(stavba_csv_path: str, del_csv_path: str) -> pd.DataFrame:
    return _load_ev_building_lookup_cached(
        stavba_csv_path,
        del_csv_path,
        os.path.getmtime(stavba_csv_path),
        os.path.getmtime(del_csv_path),
    ).copy()


@lru_cache(maxsize=4)
def _load_ev_building_value_lookup_cached(del_enota_csv_path: str, mtime: float) -> pd.DataFrame:
    del_enota_cols = ["EID_DEL_STAVBE", "POSPLOSENA_VREDNOST"]
    value_df = read_csv_flexible(del_enota_csv_path, usecols=lambda col: col in del_enota_cols)
    value_df["EID_DEL_STAVBE_KEY"] = _normalize_numeric_key_series(value_df["EID_DEL_STAVBE"])
    value_df["POSPLOSENA_VREDNOST"] = pd.to_numeric(value_df["POSPLOSENA_VREDNOST"], errors="coerce")
    value_df = value_df.dropna(subset=["EID_DEL_STAVBE_KEY", "POSPLOSENA_VREDNOST"])
    grouped = (
        value_df.groupby("EID_DEL_STAVBE_KEY", as_index=False)["POSPLOSENA_VREDNOST"].sum(min_count=1)
    )
    return grouped


def _load_ev_building_value_lookup(del_enota_csv_path: str) -> pd.DataFrame:
    return _load_ev_building_value_lookup_cached(
        del_enota_csv_path,
        os.path.getmtime(del_enota_csv_path),
    ).copy()


@lru_cache(maxsize=4)
def _load_ev_parcel_lookup_cached(parcela_csv_path: str, mtime: float) -> pd.DataFrame:
    parcela_cols = ["KO_SIFKO", "PARCELA", "POVRSINA", "BONITETA", "ODPRTOST", "RK", "RPE_OBCINE_SIFRA"]
    parcela_df = read_csv_flexible(parcela_csv_path, usecols=lambda col: col in parcela_cols)
    parcela_df["ko_key"] = _normalize_numeric_key_series(parcela_df["KO_SIFKO"])
    parcela_df["parcela_key"] = _normalize_parcel_key_series(parcela_df["PARCELA"])
    parcela_df["parcel_join_key"] = [
        _compose_join_key(ko, parcela, allow_empty_trailing=False)
        for ko, parcela in zip(parcela_df["ko_key"], parcela_df["parcela_key"], strict=False)
    ]
    parcela_df = parcela_df.dropna(subset=["parcel_join_key"])
    parcela_df = parcela_df.drop_duplicates(subset=["parcel_join_key"], keep="first")
    return parcela_df


def _load_ev_parcel_lookup(parcela_csv_path: str) -> pd.DataFrame:
    return _load_ev_parcel_lookup_cached(parcela_csv_path, os.path.getmtime(parcela_csv_path)).copy()


@lru_cache(maxsize=4)
def _load_ev_parcel_value_lookup_cached(parc_enota_csv_path: str, mtime: float) -> pd.DataFrame:
    parc_enota_cols = ["EID_PARCELA", "POSPLOSENA_VREDNOST"]
    value_df = read_csv_flexible(parc_enota_csv_path, usecols=lambda col: col in parc_enota_cols)
    value_df["EID_PARCELA_KEY"] = _normalize_numeric_key_series(value_df["EID_PARCELA"])
    value_df["POSPLOSENA_VREDNOST"] = pd.to_numeric(value_df["POSPLOSENA_VREDNOST"], errors="coerce")
    value_df = value_df.dropna(subset=["EID_PARCELA_KEY", "POSPLOSENA_VREDNOST"])
    grouped = value_df.groupby("EID_PARCELA_KEY", as_index=False)["POSPLOSENA_VREDNOST"].sum(min_count=1)
    return grouped


def _load_ev_parcel_value_lookup(parc_enota_csv_path: str) -> pd.DataFrame:
    return _load_ev_parcel_value_lookup_cached(
        parc_enota_csv_path,
        os.path.getmtime(parc_enota_csv_path),
    ).copy()


def apply_gurs_deterministic_enrichment(
    training_df: pd.DataFrame,
    *,
    upload_dir: str,
    enrichment_options: dict[str, Any] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    result = training_df.copy()
    resolved_options = resolve_enrichment_options(enrichment_options)
    discovered_sources = discover_gurs_enrichment_sources(upload_dir)
    summary: dict[str, Any] = {
        "options": resolved_options,
        "sources": {name: os.path.basename(path) for name, path in discovered_sources.items()},
        "rn": {"enabled": resolved_options["enable_rn"], "available": False, "rows_with_exact_address": 0, "rows_with_region_id": 0},
        "ev": {
            "enabled": resolved_options["enable_ev"],
            "building_available": False,
            "building_value_available": False,
            "parcel_available": False,
            "parcel_value_available": False,
            "rows_with_building_match": 0,
            "rows_with_building_value_match": 0,
            "rows_with_parcel_match": 0,
            "rows_with_parcel_value_match": 0,
        },
        "kn": {
            "enabled": resolved_options["enable_kn"],
            "available": False,
            "ggo_available": False,
            "polygon_enabled": False,
            "gpkg_ready": False,
            "rows_with_coordinates": 0,
            "rows_with_sifra_ko_match": 0,
            "rows_with_polygon_match": 0,
            "rows_with_ggo_match": 0,
        },
        "gji": {
            "enabled": resolved_options["enable_gji"],
            "available": False,
            "spatial_enabled": False,
            "rows_with_coordinates": 0,
            "vodovod_available": False,
            "kanalizacija_available": False,
            "rows_with_vodovod_distance": 0,
            "rows_with_kanalizacija_distance": 0,
            "rows_with_vodovod_nearby_100m": 0,
            "rows_with_kanalizacija_nearby_100m": 0,
        },
        "emv": {
            "enabled": resolved_options["enable_emv"],
            "available": False,
            "spatial_enabled": False,
            "gpkg_ready": False,
            "rows_with_coordinates": 0,
            "rows_with_zone_match": 0,
            "matched_by_layer": {},
        },
    }

    result["ev_benchmark_price_eur"] = pd.to_numeric(
        result.get("ev_benchmark_price_eur", np.nan),
        errors="coerce",
    )
    result["ev_benchmark_source"] = result.get("ev_benchmark_source", "unknown")

    rn_path = discovered_sources.get("rn")
    if resolved_options["enable_rn"] and rn_path is not None:
        summary["rn"]["available"] = True
        rn_df = _load_rn_lookup(rn_path)

        result["rn_address_match"] = 0
        result["eid_statisticna_regija"] = result.get("eid_statisticna_regija", np.nan)
        result["eid_naselje"] = result.get("eid_naselje", np.nan)
        result["eid_ulica"] = result.get("eid_ulica", np.nan)
        result["eid_naslov"] = result.get("eid_naslov", np.nan)

        address_join_key = [
            _compose_join_key(obcina, naselje, ulica or "", hs, dodatek or "")
            for obcina, naselje, ulica, hs, dodatek in zip(
                _normalize_numeric_key_series(result.get("rpe_obcine_sifra", pd.Series(np.nan, index=result.index))),
                _normalize_text_key_series(result.get("naselje", pd.Series(np.nan, index=result.index))),
                _normalize_text_key_series(result.get("ulica", pd.Series(np.nan, index=result.index))),
                _normalize_house_number_key_series(result.get("hisna_stevilka", pd.Series(np.nan, index=result.index))),
                _normalize_text_key_series(result.get("dodatek_hs", pd.Series(np.nan, index=result.index))),
                strict=False,
            )
        ]
        result["address_join_key"] = address_join_key
        result["address_join_key_by_name"] = [
            _compose_join_key(obcina, naselje, ulica or "", hs, dodatek or "")
            for obcina, naselje, ulica, hs, dodatek in zip(
                _normalize_text_key_series(result.get("municipality", pd.Series(np.nan, index=result.index))),
                _normalize_text_key_series(result.get("naselje", pd.Series(np.nan, index=result.index))),
                _normalize_text_key_series(result.get("ulica", pd.Series(np.nan, index=result.index))),
                _normalize_house_number_key_series(result.get("hisna_stevilka", pd.Series(np.nan, index=result.index))),
                _normalize_text_key_series(result.get("dodatek_hs", pd.Series(np.nan, index=result.index))),
                strict=False,
            )
        ]

        rn_lookup = rn_df.dropna(subset=["address_join_key"]).set_index("address_join_key")
        rn_lookup_by_name = rn_df.dropna(subset=["address_join_key_by_name"]).set_index("address_join_key_by_name")
        matched_rn = rn_lookup.reindex(result["address_join_key"]).set_axis(result.index)
        matched_rn_by_name = rn_lookup_by_name.reindex(result["address_join_key_by_name"]).set_axis(result.index)
        matched_rn = matched_rn.where(matched_rn.notna(), matched_rn_by_name)
        rn_match_mask = matched_rn["EID_NASLOV"].notna() if "EID_NASLOV" in matched_rn.columns else pd.Series(False, index=result.index)
        result.loc[rn_match_mask.values, "rn_address_match"] = 1
        for target_col, source_col in [
            ("eid_statisticna_regija", "EID_STATISTICNA_REGIJA"),
            ("eid_naselje", "EID_NASELJE"),
            ("eid_ulica", "EID_ULICA"),
            ("eid_naslov", "EID_NASLOV"),
        ]:
            if source_col in matched_rn.columns:
                result[target_col] = matched_rn[source_col].values
        if "E" in matched_rn.columns and "longitude" in result.columns:
            result["longitude"] = result["longitude"].where(
                result["longitude"].notna(),
                pd.to_numeric(matched_rn["E"], errors="coerce").values,
            )
        if "N" in matched_rn.columns and "latitude" in result.columns:
            result["latitude"] = result["latitude"].where(
                result["latitude"].notna(),
                pd.to_numeric(matched_rn["N"], errors="coerce").values,
            )

        summary["rn"]["rows_with_exact_address"] = int(result["rn_address_match"].sum())
        summary["rn"]["rows_with_region_id"] = int(pd.Series(result["eid_statisticna_regija"]).notna().sum())

    building_stavba_path = discovered_sources.get("ev_stavba")
    building_del_path = discovered_sources.get("ev_del_stavbe")
    if resolved_options["enable_ev"] and building_stavba_path is not None and building_del_path is not None:
        summary["ev"]["building_available"] = True
        ev_building_df = _load_ev_building_lookup(building_stavba_path, building_del_path)
        result["building_part_join_key"] = [
            _compose_join_key(ko, stavba, del_stavbe, allow_empty_trailing=False)
            for ko, stavba, del_stavbe in zip(
                _normalize_numeric_key_series(result.get("sifra_ko", pd.Series(np.nan, index=result.index))),
                _normalize_numeric_key_series(result.get("stevilka_stavbe", pd.Series(np.nan, index=result.index))),
                _normalize_numeric_key_series(result.get("stevilka_dela_stavbe", pd.Series(np.nan, index=result.index))),
                strict=False,
            )
        ]
        ev_lookup = ev_building_df.set_index("building_part_join_key")
        matched_ev = ev_lookup.reindex(result["building_part_join_key"])

        ev_column_map = {
            "ev_st_etaz": "ST_ETAZ",
            "ev_leto_izg_stavbe": "LETO_IZG_STA",
            "ev_leto_obn_strehe": "LETO_OBN_STREHE",
            "ev_leto_obn_fasade": "LETO_OBN_FASADE",
            "ev_id_konstrukcija": "ID_KONSTRUKCIJA",
            "ev_ima_vodovod": "IMA_VODOVOD_DN",
            "ev_ima_elektriko": "IMA_ELEKTRIKO_DN",
            "ev_ima_kanalizacijo": "IMA_KANALIZACIJO_DN",
            "ev_ima_plin": "IMA_PLIN_DN",
            "ev_id_tip_stavbe": "ID_TIP_STAVBE",
            "ev_st_stanovanj": "ST_STANOVANJ",
            "ev_st_poslovnih_prostorov": "ST_POSLOVNIH_PROSTOROV",
            "ev_pov_stavbe": "POV_STAVBE",
            "ev_del_povrsina": "POVRSINA",
            "ev_del_upor_pov": "UPOR_POV",
            "ev_leto_obn_oken": "LETO_OBN_OKEN",
            "ev_leto_obn_inst": "LETO_OBN_INST",
            "ev_del_st_nadstropja": "ST_NADSTROPJA",
            "ev_id_lega": "ID_LEGA",
            "ev_ima_dvigalo": "IMA_DVIGALO_DN",
            "ev_visina_etaze": "VISINA_ETAZE",
            "ev_id_dr_dst": "ID_DR_DST",
        }
        for target_col, source_col in ev_column_map.items():
            if source_col in matched_ev.columns:
                result[target_col] = pd.to_numeric(matched_ev[source_col], errors="coerce").values

        summary["ev"]["rows_with_building_match"] = int(matched_ev["EID_STAVBA_KEY"].notna().sum())

        building_value_path = discovered_sources.get("ev_del_stavbe_enota")
        if building_value_path is not None and "EID_DEL_STAVBE_KEY" in matched_ev.columns:
            summary["ev"]["building_value_available"] = True
            ev_building_value_df = _load_ev_building_value_lookup(building_value_path)
            building_value_lookup = ev_building_value_df.set_index("EID_DEL_STAVBE_KEY")
            matched_building_values = building_value_lookup.reindex(matched_ev["EID_DEL_STAVBE_KEY"])
            building_values = pd.to_numeric(
                matched_building_values.get("POSPLOSENA_VREDNOST"),
                errors="coerce",
            )
            building_value_mask = building_values.notna().values
            result.loc[building_value_mask, "ev_benchmark_price_eur"] = building_values.values[building_value_mask]
            result.loc[building_value_mask, "ev_benchmark_source"] = "del_stavbe_enota"
            summary["ev"]["rows_with_building_value_match"] = int(building_values.notna().sum())

    parcel_path = discovered_sources.get("ev_parcela")
    if resolved_options["enable_ev"] and parcel_path is not None:
        summary["ev"]["parcel_available"] = True
        ev_parcel_df = _load_ev_parcel_lookup(parcel_path)
        result["parcel_join_key"] = [
            _compose_join_key(ko, parcela, allow_empty_trailing=False)
            for ko, parcela in zip(
                _normalize_numeric_key_series(result.get("sifra_ko", pd.Series(np.nan, index=result.index))),
                _normalize_parcel_key_series(result.get("parcelna_stevilka", pd.Series(np.nan, index=result.index))),
                strict=False,
            )
        ]
        parcel_lookup = ev_parcel_df.set_index("parcel_join_key")
        matched_parcels = parcel_lookup.reindex(result["parcel_join_key"])
        parcel_column_map = {
            "ev_parcela_povrsina": "POVRSINA",
            "ev_boniteta": "BONITETA",
            "ev_odprtost": "ODPRTOST",
            "ev_rk": "RK",
        }
        for target_col, source_col in parcel_column_map.items():
            if source_col in matched_parcels.columns:
                result[target_col] = pd.to_numeric(matched_parcels[source_col], errors="coerce").values

        summary["ev"]["rows_with_parcel_match"] = int(matched_parcels["KO_SIFKO"].notna().sum())

        parcel_value_path = discovered_sources.get("ev_parc_enota")
        if parcel_value_path is not None and "EID_PARCELA" in matched_parcels.columns:
            summary["ev"]["parcel_value_available"] = True
            ev_parcel_value_df = _load_ev_parcel_value_lookup(parcel_value_path)
            parcel_value_lookup = ev_parcel_value_df.set_index("EID_PARCELA_KEY")
            matched_parcel_values = parcel_value_lookup.reindex(
                _normalize_numeric_key_series(matched_parcels["EID_PARCELA"])
            )
            parcel_values = pd.to_numeric(
                matched_parcel_values.get("POSPLOSENA_VREDNOST"),
                errors="coerce",
            )
            parcel_value_mask = parcel_values.notna().values & pd.isna(result["ev_benchmark_price_eur"]).values
            result.loc[parcel_value_mask, "ev_benchmark_price_eur"] = parcel_values.values[parcel_value_mask]
            result.loc[parcel_value_mask, "ev_benchmark_source"] = "parc_enota"
            summary["ev"]["rows_with_parcel_value_match"] = int(parcel_values.notna().sum())

    # Adjust EV benchmark for partial-ownership shares.
    # POSPLOSENA_VREDNOST is the value of the ENTIRE unit/parcel (100%),
    # but price_eur is the actual sale price for the SOLD share.
    # Scale benchmark down by the share so it's comparable to the target.
    ev_has_value = result["ev_benchmark_price_eur"].notna() & (result["ev_benchmark_price_eur"] > 0)
    if "prodani_delez_dela_stavbe" in result.columns:
        share = pd.to_numeric(result["prodani_delez_dela_stavbe"], errors="coerce")
        adj_mask = ev_has_value & share.notna() & (share > 0) & (share < 1)
        result.loc[adj_mask, "ev_benchmark_price_eur"] = (
            result.loc[adj_mask, "ev_benchmark_price_eur"] * share[adj_mask]
        )
    if "prodani_delez_parcele" in result.columns:
        parcel_share = pd.to_numeric(result["prodani_delez_parcele"], errors="coerce")
        parc_adj_mask = (
            ev_has_value
            & (result["ev_benchmark_source"] == "parc_enota")
            & parcel_share.notna()
            & (parcel_share > 0)
            & (parcel_share < 1)
        )
        result.loc[parc_adj_mask, "ev_benchmark_price_eur"] = (
            result.loc[parc_adj_mask, "ev_benchmark_price_eur"] * parcel_share[parc_adj_mask]
        )

    result["ev_benchmark_price_per_m2"] = (
        pd.to_numeric(result["ev_benchmark_price_eur"], errors="coerce")
        / pd.to_numeric(result.get("size_m2"), errors="coerce").clip(lower=1)
    )
    result.loc[result["ev_benchmark_price_eur"].isna(), "ev_benchmark_source"] = "unknown"

    if resolved_options["enable_kn"]:
        result, kn_summary = _apply_kn_polygon_enrichment(result, discovered_sources=discovered_sources)
        kn_summary["enabled"] = True
        summary["kn"] = kn_summary

    if resolved_options["enable_gji"]:
        result, gji_summary = _apply_gji_infrastructure_enrichment(result, discovered_sources=discovered_sources)
        gji_summary["enabled"] = True
        summary["gji"] = gji_summary

    if resolved_options["enable_emv"]:
        result, emv_summary = _apply_emv_spatial_enrichment(result, discovered_sources=discovered_sources)
        emv_summary["enabled"] = True
        summary["emv"] = emv_summary

    for helper_col in ["address_join_key", "building_part_join_key", "parcel_join_key"]:
        if helper_col in result.columns:
            result = result.drop(columns=[helper_col])

    return result, summary


def enrich_training_df(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived features: statistical_region, building_age, log_size_m2."""
    result = df.copy()

    if "municipality" in result.columns:
        result["municipality"] = result["municipality"].apply(
            lambda value: format_municipality_label(clean_display_text(value)) or "unknown"
        )
        result["municipality_normalized"] = result["municipality"].apply(normalize_municipality_name)
        result["statistical_region"] = result["municipality_normalized"].apply(lookup_region)

    if "property_type" in result.columns:
        result["property_type"] = result["property_type"].apply(normalize_text)

    if "year_built" in result.columns:
        current_year = pd.Timestamp.now().year
        result["building_age"] = current_year - pd.to_numeric(result["year_built"], errors="coerce")
        result["building_age"] = result["building_age"].clip(lower=0)
    else:
        result["building_age"] = np.nan

    if "size_m2" in result.columns:
        result["log_size_m2"] = np.log1p(pd.to_numeric(result["size_m2"], errors="coerce").fillna(0).clip(lower=0))
    else:
        result["log_size_m2"] = np.nan

    for col in [
        "num_prostori",
        "has_klet",
        "has_garaza",
        "has_terasa",
        "has_shramba",
        "has_parking",
        "ddv_vkljucen",
    ]:
        if col not in result.columns:
            result[col] = 0

    if "stavba_je_dokoncana" not in result.columns:
        result["stavba_je_dokoncana"] = 1
    if "uporabna_povrsina" not in result.columns:
        result["uporabna_povrsina"] = np.nan
    if "lega_v_stavbi" not in result.columns:
        result["lega_v_stavbi"] = "unknown"
    if "prodani_delez_parcele" not in result.columns:
        result["prodani_delez_parcele"] = np.nan
    if "prodani_delez_dela_stavbe" not in result.columns:
        result["prodani_delez_dela_stavbe"] = np.nan
    if "gradbena_faza" not in result.columns:
        result["gradbena_faza"] = np.nan
    if "stopnja_ddv" not in result.columns:
        result["stopnja_ddv"] = np.nan
    if "evidentiranost_dela_stavbe" not in result.columns:
        result["evidentiranost_dela_stavbe"] = np.nan
    if "atrij" not in result.columns:
        result["atrij"] = np.nan
    for col in ["ime_ko", "naselje", "vrsta_dela_stavbe", "vrsta_zemljisca", "vrsta_kupoprodajnega_posla"]:
        if col not in result.columns:
            result[col] = "unknown"
    if "transaction_year" not in result.columns:
        result["transaction_year"] = pd.Timestamp.now().year
    if "transaction_quarter" not in result.columns:
        result["transaction_quarter"] = np.nan
    if "novogradnja" not in result.columns:
        result["novogradnja"] = 0

    return result


def prepare_training_csv(
    source_csv_path: str,
    column_map: dict[str, str],
    output_csv_path: str,
) -> dict[str, Any]:
    df = read_csv_flexible(source_csv_path)
    renamed = df.rename(columns=column_map)

    required = [
        "size_m2",
        "rooms",
        "year_built",
        "floor",
        "latitude",
        "longitude",
        "municipality",
        "property_type",
        "price_eur",
    ]
    missing = [col for col in required if col not in renamed.columns]
    if missing:
        raise ValueError(f"Missing columns after mapping: {', '.join(missing)}")

    optional = [
        "prodani_delez_parcele",
        "prodani_delez_dela_stavbe",
        "gradbena_faza",
        "stopnja_ddv",
        "evidentiranost_dela_stavbe",
        "atrij",
        "ime_ko",
        "naselje",
        "vrsta_dela_stavbe",
        "vrsta_zemljisca",
        "vrsta_kupoprodajnega_posla",
    ]
    selected = required + [col for col in optional if col in renamed.columns]

    training_df = renamed[selected].copy()
    training_df = enrich_training_df(training_df)

    os.makedirs(os.path.dirname(output_csv_path), exist_ok=True)
    training_df.to_csv(output_csv_path, index=False)
    _write_training_metadata(
        output_csv_path,
        {
            "source": "mapped_csv",
            "rows": len(training_df),
            "columns": list(training_df.columns),
        },
    )

    return {
        "output_csv_path": output_csv_path,
        "rows": len(training_df),
        "columns": list(training_df.columns),
    }


def _training_metadata_path(csv_path: str) -> str:
    return f"{csv_path}.metadata.json"


def _write_training_metadata(csv_path: str, metadata: dict[str, Any]) -> None:
    metadata_path = _training_metadata_path(csv_path)
    os.makedirs(os.path.dirname(metadata_path), exist_ok=True)
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=True, indent=2)


def load_training_metadata(csv_path: str) -> dict[str, Any] | None:
    metadata_path = _training_metadata_path(csv_path)
    if not os.path.exists(metadata_path):
        return None
    with open(metadata_path, encoding="utf-8") as f:
        return json.load(f)


def _append_stage(stage_stats: list[dict[str, Any]], stage: str, rows: int, **extra: Any) -> None:
    previous_rows = stage_stats[-1]["rows"] if stage_stats else None
    entry = {
        "stage": stage,
        "rows": int(rows),
        "dropped_since_previous": int(max((previous_rows - rows), 0)) if previous_rows is not None else 0,
    }
    entry.update(extra)
    stage_stats.append(entry)


def _aggregate_stage_sequences(stage_sequences: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    ordered: list[str] = []
    by_stage: dict[str, dict[str, Any]] = {}

    for sequence in stage_sequences:
        for item in sequence:
            stage = str(item.get("stage"))
            if stage not in by_stage:
                ordered.append(stage)
                by_stage[stage] = {
                    "stage": stage,
                    "rows": 0,
                    "dropped_since_previous": 0,
                    "reports": 0,
                }
            by_stage[stage]["rows"] += int(item.get("rows", 0) or 0)
            by_stage[stage]["dropped_since_previous"] += int(item.get("dropped_since_previous", 0) or 0)
            by_stage[stage]["reports"] += 1

    return [by_stage[stage] for stage in ordered]


# ── ZIP extraction ──────────────────────────────────────────────────


def _safe_extractall(archive: zipfile.ZipFile, dest: str, reserve_bytes: int = 0) -> None:
    """Extract ZIP members after verifying none escape the destination directory."""
    dest = os.path.realpath(dest)
    required_bytes = sum(info.file_size for info in archive.infolist() if not info.is_dir())
    ensure_directory_headroom(dest, required_bytes, reserve_bytes)
    for member in archive.namelist():
        member_path = os.path.realpath(os.path.join(dest, member))
        if not member_path.startswith(dest + os.sep) and member_path != dest:
            raise ValueError(f"ZIP member would escape target directory: {member}")
    archive.extractall(dest)


def _expand_nested_zips(extract_dir: str, reserve_bytes: int = 0) -> None:
    processed_archives: set[str] = set()

    while True:
        discovered_any = False
        for root, _, files in os.walk(extract_dir):
            for fname in files:
                if not fname.lower().endswith('.zip'):
                    continue

                nested_path = os.path.realpath(os.path.join(root, fname))
                if nested_path in processed_archives:
                    continue

                processed_archives.add(nested_path)
                discovered_any = True

                nested_dir = os.path.join(root, f"inner_{os.path.splitext(fname)[0]}")
                os.makedirs(nested_dir, exist_ok=True)
                try:
                    with zipfile.ZipFile(nested_path, 'r') as nested:
                        _safe_extractall(nested, nested_dir, reserve_bytes)
                except (zipfile.BadZipFile, ValueError):
                    continue

        if not discovered_any:
            break


def _quote_sql_identifier(identifier: str) -> str:
    return '"' + str(identifier).replace('"', '""') + '"'


def inspect_gpkg(gpkg_path: str, preview_rows: int = 8) -> dict[str, Any]:
    with sqlite3.connect(gpkg_path) as conn:
        layer_rows = conn.execute(
            """
            SELECT c.table_name, c.data_type, COALESCE(g.column_name, '') AS geometry_column
            FROM gpkg_contents c
            LEFT JOIN gpkg_geometry_columns g ON g.table_name = c.table_name
            WHERE c.data_type IN ('features', 'attributes')
            ORDER BY c.table_name
            """
        ).fetchall()

        if not layer_rows:
            fallback_tables = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'gpkg_%'
                  AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall()
            layer_rows = [(name, 'table', '') for (name,) in fallback_tables]

        layers: list[dict[str, Any]] = []
        for table_name, data_type, geometry_column in layer_rows:
            table_info = conn.execute(f"PRAGMA table_info({_quote_sql_identifier(table_name)})").fetchall()
            column_names = [row[1] for row in table_info]
            layers.append(
                {
                    'table_name': table_name,
                    'data_type': data_type,
                    'geometry_column': geometry_column or None,
                    'columns': [name for name in column_names if name != geometry_column],
                }
            )

        if len(layers) == 1 and preview_rows > 0:
            layer = layers[0]
            selected_columns = layer['columns'][: min(len(layer['columns']), 24)]
            if selected_columns:
                select_list = ', '.join(_quote_sql_identifier(name) for name in selected_columns)
                df = pd.read_sql_query(
                    f"SELECT {select_list} FROM {_quote_sql_identifier(layer['table_name'])} LIMIT {int(preview_rows)}",
                    conn,
                )
                total_rows = conn.execute(
                    f"SELECT COUNT(*) FROM {_quote_sql_identifier(layer['table_name'])}"
                ).fetchone()[0]
                return {
                    'layers': layers,
                    'columns': list(df.columns),
                    'rows': df.fillna('').to_dict(orient='records'),
                    'total_rows': int(total_rows),
                }

        summary_rows = [
            {
                'layer_name': layer['table_name'],
                'data_type': layer['data_type'],
                'geometry_column': layer['geometry_column'] or '',
                'columns': ', '.join(layer['columns'][:12]),
            }
            for layer in layers
        ]
        return {
            'layers': layers,
            'columns': ['layer_name', 'data_type', 'geometry_column', 'columns'],
            'rows': summary_rows,
            'total_rows': len(summary_rows),
        }


def extract_zip_csvs(zip_path: str, upload_dir: str, reserve_bytes: int = 0) -> list[str]:
    """Extract a ZIP (incl. nested ZIPs) and return paths to all CSV files."""
    csv_paths, _ = extract_zip_supported_files(zip_path, upload_dir, reserve_bytes)
    return csv_paths


def extract_zip_supported_files(zip_path: str, upload_dir: str, reserve_bytes: int = 0) -> tuple[list[str], list[str]]:
    """Extract a ZIP (incl. nested ZIPs) and return paths to CSV and GeoPackage files."""
    extract_dir = os.path.join(upload_dir, f"unzipped_{uuid.uuid4().hex}")
    os.makedirs(extract_dir, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            _safe_extractall(archive, extract_dir, reserve_bytes)

        _expand_nested_zips(extract_dir, reserve_bytes)

        csv_paths: list[str] = []
        gpkg_paths: list[str] = []
        for root, _, files in os.walk(extract_dir):
            for fname in files:
                if fname.lower().endswith(".csv"):
                    src = os.path.join(root, fname)
                    safe_name = fname.replace("/", "_").replace("\\", "_")
                    dst = os.path.join(upload_dir, f"{uuid.uuid4().hex}_{safe_name}")
                    shutil.move(src, dst)
                    csv_paths.append(dst)
                elif fname.lower().endswith(".gpkg"):
                    src = os.path.join(root, fname)
                    safe_name = fname.replace("/", "_").replace("\\", "_")
                    dst = os.path.join(upload_dir, f"{uuid.uuid4().hex}_{safe_name}")
                    shutil.move(src, dst)
                    gpkg_paths.append(dst)
        return csv_paths, gpkg_paths
    finally:
        shutil.rmtree(extract_dir, ignore_errors=True)


def extract_zip_all(zip_path: str, upload_dir: str, reserve_bytes: int = 0) -> str:
    """Extract ZIP (incl. nested ZIPs) and return the extraction directory."""
    extract_dir = os.path.join(upload_dir, f"unzipped_{uuid.uuid4().hex}")
    os.makedirs(extract_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as archive:
        _safe_extractall(archive, extract_dir, reserve_bytes)

    _expand_nested_zips(extract_dir, reserve_bytes)
    return extract_dir


def _get_optional_geopandas() -> Any | None:
    try:
        import geopandas as gpd
    except ImportError:
        return None
    return gpd


@lru_cache(maxsize=16)
def _extract_vector_zip_cached(source_path: str, mtime: float) -> str:
    return extract_zip_all(source_path, os.path.dirname(source_path))


def _find_extracted_vector_paths(
    extract_dir: str,
    *,
    suffixes: tuple[str, ...] = (".gpkg", ".shp"),
) -> list[str]:
    candidates: list[str] = []
    for root, _, files in os.walk(extract_dir):
        for name in files:
            if name.lower().endswith(suffixes):
                candidates.append(os.path.join(root, name))
    return candidates


@lru_cache(maxsize=4)
def _resolve_emv_gpkg_path_cached(source_path: str, mtime: float) -> str | None:
    lower_source_path = source_path.lower()
    if lower_source_path.endswith((".gpkg", ".shp")):
        return source_path
    if not lower_source_path.endswith(".zip"):
        return None

    extract_dir = _extract_vector_zip_cached(source_path, mtime)
    gpkg_paths = _find_extracted_vector_paths(extract_dir, suffixes=(".gpkg",))
    if gpkg_paths:
        matching = [path for path in gpkg_paths if "emv_vredn_cone" in os.path.basename(path).lower()]
        candidates = matching or gpkg_paths
        return max(candidates, key=os.path.getmtime)

    shp_paths = _find_extracted_vector_paths(extract_dir, suffixes=(".shp",))
    if not shp_paths:
        return None

    return extract_dir


def _resolve_emv_gpkg_path(source_path: str) -> str | None:
    return _resolve_emv_gpkg_path_cached(source_path, os.path.getmtime(source_path))


@lru_cache(maxsize=16)
def _resolve_vector_gpkg_path_cached(source_path: str, mtime: float, preferred_name: str) -> str | None:
    lower_source_path = source_path.lower()
    if lower_source_path.endswith((".gpkg", ".shp")):
        return source_path
    if not lower_source_path.endswith(".zip"):
        return None

    extract_dir = _extract_vector_zip_cached(source_path, mtime)
    vector_paths = _find_extracted_vector_paths(extract_dir)
    if not vector_paths:
        return None

    preferred = [
        path for path in vector_paths if preferred_name and preferred_name.lower() in os.path.basename(path).lower()
    ]
    candidates = preferred or vector_paths
    return max(candidates, key=os.path.getmtime)


def _resolve_vector_gpkg_path(source_path: str, preferred_name: str = "") -> str | None:
    return _resolve_vector_gpkg_path_cached(source_path, os.path.getmtime(source_path), preferred_name)


@lru_cache(maxsize=32)
def _detect_gpkg_default_layer_cached(gpkg_path: str, mtime: float) -> str | None:
    if not gpkg_path.lower().endswith(".gpkg"):
        return None
    inspection = inspect_gpkg(gpkg_path, preview_rows=0)
    layers = inspection.get("layers") or []
    if not layers:
        return None
    return str(layers[0].get("table_name") or "") or None


def _detect_gpkg_default_layer(gpkg_path: str) -> str | None:
    return _detect_gpkg_default_layer_cached(gpkg_path, os.path.getmtime(gpkg_path))


def _normalize_vector_layer(layer_gdf: Any, *, keep_columns: list[str] | None = None) -> Any:
    if layer_gdf is None or layer_gdf.empty or "geometry" not in layer_gdf.columns:
        return None

    if keep_columns is not None:
        selected_columns = [column for column in keep_columns if column in layer_gdf.columns]
        if "geometry" not in selected_columns:
            selected_columns.append("geometry")
        layer_gdf = layer_gdf[selected_columns].copy()

    layer_gdf = layer_gdf[layer_gdf.geometry.notna()].copy()
    if layer_gdf.empty:
        return None

    try:
        if layer_gdf.crs is None:
            layer_gdf = layer_gdf.set_crs(_EMV_TARGET_CRS, allow_override=True)
        elif str(layer_gdf.crs) != _EMV_TARGET_CRS:
            layer_gdf = layer_gdf.to_crs(_EMV_TARGET_CRS)
    except Exception as exc:
        logger.warning("Failed to normalize CRS for layer: %s", exc)
        return None

    return layer_gdf


def _read_vector_table(gpkg_path: str, layer_name: str | None = None, *, columns: list[str] | None = None) -> pd.DataFrame | None:
    gpd = _get_optional_geopandas()
    if gpd is None:
        raise RuntimeError("geopandas is not installed")

    is_gpkg = gpkg_path.lower().endswith(".gpkg")
    selected_layer = (layer_name or _detect_gpkg_default_layer(gpkg_path)) if is_gpkg else None
    if is_gpkg and not selected_layer:
        return None

    read_kwargs: dict[str, Any] = {
        "engine": "pyogrio",
        "ignore_geometry": True,
    }
    if is_gpkg:
        read_kwargs["layer"] = selected_layer
    if columns is not None:
        read_kwargs["columns"] = columns

    try:
        layer_df = gpd.read_file(gpkg_path, **read_kwargs)
    except Exception as exc:
        logger.debug("Failed to read vector table %s from %s: %s", selected_layer, gpkg_path, exc)
        return None

    if layer_df is None or layer_df.empty:
        return None

    return pd.DataFrame(layer_df)


def _load_vector_layer(
    gpkg_path: str,
    layer_name: str | None = None,
    *,
    columns: list[str] | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> Any:
    gpd = _get_optional_geopandas()
    if gpd is None:
        raise RuntimeError("geopandas is not installed")

    is_gpkg = gpkg_path.lower().endswith(".gpkg")
    selected_layer = (layer_name or _detect_gpkg_default_layer(gpkg_path)) if is_gpkg else None
    if is_gpkg and not selected_layer:
        return None

    read_kwargs: dict[str, Any] = {
        "engine": "pyogrio",
    }
    if is_gpkg:
        read_kwargs["layer"] = selected_layer
    if columns is not None:
        read_kwargs["columns"] = columns
    if bbox is not None:
        read_kwargs["bbox"] = bbox

    try:
        layer_gdf = gpd.read_file(gpkg_path, **read_kwargs)
    except Exception as exc:
        logger.debug("Failed to load vector layer %s from %s: %s", selected_layer, gpkg_path, exc)
        if columns is not None:
            fallback_kwargs = dict(read_kwargs)
            fallback_kwargs.pop("columns", None)
            try:
                layer_gdf = gpd.read_file(gpkg_path, **fallback_kwargs)
            except Exception as fallback_exc:
                logger.debug("Fallback vector layer load failed for %s from %s: %s", selected_layer, gpkg_path, fallback_exc)
                return None
        else:
            return None

    return _normalize_vector_layer(layer_gdf, keep_columns=columns)


def _resolve_shapefile_path(extract_dir: str, preferred_name: str) -> str | None:
    preferred_key = preferred_name.lower()
    shapefiles = _find_extracted_vector_paths(extract_dir, suffixes=(".shp",))
    preferred = [
        path for path in shapefiles if preferred_key and preferred_key in os.path.splitext(os.path.basename(path))[0].lower()
    ]
    candidates = preferred or shapefiles
    if not candidates:
        return None
    return max(candidates, key=os.path.getmtime)


def _spatial_bbox_for_rows(
    frame: pd.DataFrame,
    row_index: pd.Index,
    *,
    padding_m: float = 0.0,
) -> tuple[float, float, float, float] | None:
    if row_index.empty:
        return None

    coordinates = frame.loc[row_index, ["longitude", "latitude"]].copy()
    coordinates["longitude"] = pd.to_numeric(coordinates["longitude"], errors="coerce")
    coordinates["latitude"] = pd.to_numeric(coordinates["latitude"], errors="coerce")
    coordinates = coordinates.dropna(subset=["longitude", "latitude"])
    if coordinates.empty:
        return None

    min_x = float(coordinates["longitude"].min()) - padding_m
    min_y = float(coordinates["latitude"].min()) - padding_m
    max_x = float(coordinates["longitude"].max()) + padding_m
    max_y = float(coordinates["latitude"].max()) + padding_m
    return (min_x, min_y, max_x, max_y)


def _iter_spatial_batches(frame: pd.DataFrame, row_index: pd.Index) -> list[pd.Index]:
    if row_index.empty:
        return []

    coordinates = frame.loc[row_index, ["longitude", "latitude"]].copy()
    coordinates["longitude"] = pd.to_numeric(coordinates["longitude"], errors="coerce")
    coordinates["latitude"] = pd.to_numeric(coordinates["latitude"], errors="coerce")
    coordinates = coordinates.dropna(subset=["longitude", "latitude"])
    if coordinates.empty:
        return []

    coordinates["tile_x"] = np.floor(coordinates["longitude"] / _SPATIAL_TILE_SIZE_M).astype("int64")
    coordinates["tile_y"] = np.floor(coordinates["latitude"] / _SPATIAL_TILE_SIZE_M).astype("int64")

    batches: list[pd.Index] = []
    for _tile_key, tile_rows in coordinates.groupby(["tile_x", "tile_y"], sort=False):
        tile_index = tile_rows.index.to_list()
        for start in range(0, len(tile_index), _SPATIAL_BATCH_SIZE):
            batches.append(pd.Index(tile_index[start : start + _SPATIAL_BATCH_SIZE]))
    return batches


def _build_points_gdf(frame: pd.DataFrame, row_index: pd.Index) -> Any:
    gpd = _get_optional_geopandas()
    if gpd is None or row_index.empty:
        return None

    points = frame.loc[row_index, ["longitude", "latitude"]].copy()
    points["longitude"] = pd.to_numeric(points["longitude"], errors="coerce")
    points["latitude"] = pd.to_numeric(points["latitude"], errors="coerce")
    points = points.dropna(subset=["longitude", "latitude"])
    if points.empty:
        return None

    return gpd.GeoDataFrame(
        points,
        geometry=gpd.points_from_xy(points["longitude"], points["latitude"]),
        crs=_EMV_TARGET_CRS,
    )


def _coordinate_numeric_series(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame.get(column, pd.Series(np.nan, index=frame.index)), errors="coerce")


def _nearest_distances_to_layer(
    frame: pd.DataFrame,
    row_index: pd.Index,
    *,
    gpkg_path: str,
    layer_name: str | None = None,
) -> pd.Series:
    if row_index.empty:
        return pd.Series(np.nan, index=row_index, dtype="float64")

    gpd = _get_optional_geopandas()
    if gpd is None:
        return pd.Series(np.nan, index=row_index, dtype="float64")

    distances = pd.Series(np.nan, index=row_index, dtype="float64")
    for batch_index in _iter_spatial_batches(frame, row_index):
        bbox = _spatial_bbox_for_rows(frame, batch_index, padding_m=_GJI_NEARBY_DISTANCE_M + _SPATIAL_BBOX_PADDING_M)
        layer_gdf = _load_vector_layer(gpkg_path, layer_name, columns=[], bbox=bbox)
        points_gdf = _build_points_gdf(frame, batch_index)
        if layer_gdf is None or layer_gdf.empty or points_gdf is None or points_gdf.empty:
            continue

        joined = gpd.sjoin_nearest(
            points_gdf,
            layer_gdf[["geometry"]],
            how="left",
            distance_col="_distance_m",
        )
        joined = joined.loc[~joined.index.duplicated(keep="first")]
        distances.loc[batch_index] = pd.to_numeric(joined.get("_distance_m"), errors="coerce").reindex(batch_index).values

    return distances


def _apply_kn_polygon_enrichment(
    training_df: pd.DataFrame,
    *,
    discovered_sources: dict[str, str],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    result = training_df.copy()
    summary: dict[str, Any] = {
        "available": False,
        "ggo_available": False,
        "polygon_enabled": False,
        "gpkg_ready": False,
        "rows_with_coordinates": 0,
        "rows_with_sifra_ko_match": 0,
        "rows_with_polygon_match": 0,
        "rows_with_ggo_match": 0,
    }

    for numeric_column in ["kn_ko_polygon_match", "kn_in_ggo", "kn_ggo_openness"]:
        result[numeric_column] = pd.to_numeric(result.get(numeric_column, np.nan), errors="coerce")
    for categorical_column in ["kn_ko_name", "kn_ko_eid", "kn_ko_date", "kn_ggo_section"]:
        if categorical_column not in result.columns:
            result[categorical_column] = pd.Series(pd.NA, index=result.index, dtype="object")

    source_path = discovered_sources.get("kn_kat_obcine")
    if source_path is None:
        return result, summary

    summary["available"] = True

    gpd = _get_optional_geopandas()
    if gpd is None:
        summary["reason"] = "geopandas_not_installed"
        return result, summary

    gpkg_path = _resolve_vector_gpkg_path(source_path, "kat_obcine")
    if gpkg_path is None:
        summary["reason"] = "gpkg_not_found"
        return result, summary

    ko_lookup = _read_vector_table(
        gpkg_path,
        _KN_KO_LAYER,
        columns=["SIFKO", "NAZIV", "EID_KATAST", "DATUM_SYS"],
    )
    if ko_lookup is None or ko_lookup.empty:
        summary["reason"] = "layer_not_found"
        return result, summary

    summary["gpkg_ready"] = True
    summary["gpkg_file"] = os.path.basename(gpkg_path)

    ko_lookup["ko_key"] = _normalize_numeric_key_series(ko_lookup.get("SIFKO", pd.Series(dtype="object")))
    ko_lookup = ko_lookup.dropna(subset=["ko_key"]).drop_duplicates(subset=["ko_key"], keep="first")
    ko_lookup = ko_lookup.set_index("ko_key")

    training_ko_key = _normalize_numeric_key_series(result.get("sifra_ko", pd.Series(np.nan, index=result.index)))
    matched_ko = ko_lookup.reindex(training_ko_key)
    if "NAZIV" in matched_ko.columns:
        result["kn_ko_name"] = matched_ko["NAZIV"].values
    if "EID_KATAST" in matched_ko.columns:
        result["kn_ko_eid"] = matched_ko["EID_KATAST"].values
    if "DATUM_SYS" in matched_ko.columns:
        result["kn_ko_date"] = matched_ko["DATUM_SYS"].values
    summary["rows_with_sifra_ko_match"] = int(pd.Series(result["kn_ko_name"]).notna().sum())

    longitude = _coordinate_numeric_series(result, "longitude")
    latitude = _coordinate_numeric_series(result, "latitude")
    point_index = result.index[longitude.notna() & latitude.notna()]
    summary["rows_with_coordinates"] = int(len(point_index))
    unresolved_index = point_index[result.loc[point_index, "kn_ko_name"].isna()]

    if not unresolved_index.empty:
        summary["polygon_enabled"] = True
        for batch_index in _iter_spatial_batches(result, unresolved_index):
            bbox = _spatial_bbox_for_rows(result, batch_index, padding_m=_SPATIAL_BBOX_PADDING_M)
            ko_gdf = _load_vector_layer(
                gpkg_path,
                _KN_KO_LAYER,
                columns=["SIFKO", "NAZIV", "EID_KATAST", "DATUM_SYS"],
                bbox=bbox,
            )
            points_gdf = _build_points_gdf(result, batch_index)
            if ko_gdf is None or ko_gdf.empty or points_gdf is None or points_gdf.empty:
                continue

            spatial_join = gpd.sjoin(
                points_gdf,
                ko_gdf,
                how="left",
                predicate="intersects",
            )
            spatial_join = spatial_join.loc[~spatial_join.index.duplicated(keep="first")]
            polygon_mask = spatial_join["SIFKO"].notna() if "SIFKO" in spatial_join.columns else pd.Series(False, index=spatial_join.index)
            if not polygon_mask.any():
                continue
            idx = spatial_join.index[polygon_mask]
            result.loc[idx, "kn_ko_polygon_match"] = 1
            if "NAZIV" in spatial_join.columns:
                result.loc[idx, "kn_ko_name"] = spatial_join.loc[idx, "NAZIV"].values
            if "EID_KATAST" in spatial_join.columns:
                result.loc[idx, "kn_ko_eid"] = spatial_join.loc[idx, "EID_KATAST"].values
            if "DATUM_SYS" in spatial_join.columns:
                result.loc[idx, "kn_ko_date"] = spatial_join.loc[idx, "DATUM_SYS"].values
            summary["rows_with_polygon_match"] += int(len(idx))

    ggo_source_path = discovered_sources.get("kn_ggo")
    if ggo_source_path is not None and not point_index.empty:
        summary["ggo_available"] = True
        ggo_gpkg_path = _resolve_vector_gpkg_path(ggo_source_path, "ggo")
        if ggo_gpkg_path is not None:
            for batch_index in _iter_spatial_batches(result, point_index):
                bbox = _spatial_bbox_for_rows(result, batch_index, padding_m=_SPATIAL_BBOX_PADDING_M)
                ggo_gdf = _load_vector_layer(
                    ggo_gpkg_path,
                    _KN_GGO_LAYER,
                    columns=["ODSEK", "ODPRTOST"],
                    bbox=bbox,
                )
                points_gdf = _build_points_gdf(result, batch_index)
                if ggo_gdf is None or ggo_gdf.empty or points_gdf is None or points_gdf.empty:
                    continue

                ggo_join = gpd.sjoin(
                    points_gdf,
                    ggo_gdf,
                    how="left",
                    predicate="intersects",
                )
                ggo_join = ggo_join.loc[~ggo_join.index.duplicated(keep="first")]
                ggo_mask = ggo_join["ODSEK"].notna() if "ODSEK" in ggo_join.columns else pd.Series(False, index=ggo_join.index)
                if not ggo_mask.any():
                    continue
                idx = ggo_join.index[ggo_mask]
                result.loc[idx, "kn_in_ggo"] = 1
                if "ODPRTOST" in ggo_join.columns:
                    result.loc[idx, "kn_ggo_openness"] = pd.to_numeric(ggo_join.loc[idx, "ODPRTOST"], errors="coerce").values
                if "ODSEK" in ggo_join.columns:
                    result.loc[idx, "kn_ggo_section"] = ggo_join.loc[idx, "ODSEK"].values
                summary["rows_with_ggo_match"] += int(len(idx))

    result["kn_ko_polygon_match"] = pd.to_numeric(result["kn_ko_polygon_match"], errors="coerce").fillna(0)
    result["kn_in_ggo"] = pd.to_numeric(result["kn_in_ggo"], errors="coerce").fillna(0)
    return result, summary


def _apply_gji_infrastructure_enrichment(
    training_df: pd.DataFrame,
    *,
    discovered_sources: dict[str, str],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    result = training_df.copy()
    summary: dict[str, Any] = {
        "available": False,
        "spatial_enabled": False,
        "rows_with_coordinates": 0,
    }
    for _lbl in ["vodovod", "kanalizacija", "elektrika", "plin", "ceste", "toplota"]:
        summary[f"{_lbl}_available"] = False
        summary[f"rows_with_{_lbl}_distance"] = 0
        summary[f"rows_with_{_lbl}_nearby_100m"] = 0

    _gji_types = ["vodovod", "kanalizacija", "elektrika", "plin", "ceste", "toplota"]
    for label in _gji_types:
        for suffix in ["distance_m", "nearby_100m"]:
            col = f"gji_{label}_{suffix}"
            result[col] = pd.to_numeric(result.get(col, np.nan), errors="coerce")

    longitude = _coordinate_numeric_series(result, "longitude")
    latitude = _coordinate_numeric_series(result, "latitude")
    point_index = result.index[longitude.notna() & latitude.notna()]
    summary["rows_with_coordinates"] = int(len(point_index))
    if point_index.empty:
        return result, summary

    if _get_optional_geopandas() is None:
        summary["reason"] = "geopandas_not_installed"
        return result, summary

    summary["spatial_enabled"] = True

    for source_name, layer_label in [
        ("gji_vodovod", "vodovod"),
        ("gji_kanalizacija", "kanalizacija"),
        ("gji_elektrika", "elektrika"),
        ("gji_plin", "plin"),
        ("gji_ceste", "ceste"),
        ("gji_toplota", "toplota"),
    ]:
        source_path = discovered_sources.get(source_name)
        if source_path is None:
            continue

        summary["available"] = True
        summary[f"{layer_label}_available"] = True
        gpkg_path = _resolve_vector_gpkg_path(source_path, layer_label)
        if gpkg_path is None:
            continue

        distance_series = _nearest_distances_to_layer(result, point_index, gpkg_path=gpkg_path)
        distance_col = f"gji_{layer_label}_distance_m"
        nearby_col = f"gji_{layer_label}_nearby_100m"
        nearby_series = (distance_series <= _GJI_NEARBY_DISTANCE_M).astype(float)
        result.loc[point_index, distance_col] = distance_series.values
        result.loc[point_index, nearby_col] = nearby_series.values
        summary[f"rows_with_{layer_label}_distance"] = int(distance_series.notna().sum())
        summary[f"rows_with_{layer_label}_nearby_100m"] = int((nearby_series > 0).sum())

    return result, summary


def _load_emv_layer(
    gpkg_path: str,
    layer_name: str,
    *,
    bbox: tuple[float, float, float, float] | None = None,
) -> Any:
    if os.path.isdir(gpkg_path):
        shp_path = _resolve_shapefile_path(gpkg_path, layer_name)
        if shp_path is None:
            return None
        gpkg_path = shp_path
        layer_name = None

    layer_gdf = _load_vector_layer(
        gpkg_path,
        layer_name,
        columns=["IME", "MODEL", "ID", "ST_RAVNI", "DAT_VELJ"],
        bbox=bbox,
    )
    if layer_gdf is None or layer_gdf.empty:
        return None

    if "ST_RAVNI" in layer_gdf.columns:
        layer_gdf["ST_RAVNI"] = pd.to_numeric(layer_gdf["ST_RAVNI"], errors="coerce")
    return layer_gdf


def _match_emv_layer_to_rows(
    frame: pd.DataFrame,
    row_index: pd.Index,
    *,
    gpkg_path: str,
    layer_name: str,
) -> pd.DataFrame:
    if row_index.empty:
        return pd.DataFrame(index=row_index)

    gpd = _get_optional_geopandas()
    if gpd is None:
        return pd.DataFrame(index=row_index)

    matched_batches: list[pd.DataFrame] = []
    for batch_index in _iter_spatial_batches(frame, row_index):
        bbox = _spatial_bbox_for_rows(frame, batch_index, padding_m=_SPATIAL_BBOX_PADDING_M)
        layer_gdf = _load_emv_layer(gpkg_path, layer_name, bbox=bbox)
        if layer_gdf is None or layer_gdf.empty:
            continue

        points = frame.loc[batch_index, ["longitude", "latitude"]].copy()
        points_gdf = gpd.GeoDataFrame(
            points,
            geometry=gpd.points_from_xy(points["longitude"], points["latitude"]),
            crs=_EMV_TARGET_CRS,
        )

        joined = gpd.sjoin(points_gdf, layer_gdf, how="left", predicate="intersects")
        joined = joined.loc[~joined.index.duplicated(keep="first")]

        columns = [column for column in ["IME", "MODEL", "ID", "ST_RAVNI", "DAT_VELJ"] if column in joined.columns]
        if columns:
            matched_batches.append(joined[columns].reindex(batch_index))

    if not matched_batches:
        return pd.DataFrame(index=row_index)

    return pd.concat(matched_batches).reindex(row_index)


def _apply_emv_spatial_enrichment(
    training_df: pd.DataFrame,
    *,
    discovered_sources: dict[str, str],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    result = training_df.copy()
    summary: dict[str, Any] = {
        "available": False,
        "spatial_enabled": False,
        "gpkg_ready": False,
        "rows_with_coordinates": 0,
        "rows_with_zone_match": 0,
        "matched_by_layer": {},
    }

    for numeric_column in ["emv_zone_match", "emv_zone_level"]:
        result[numeric_column] = pd.to_numeric(result.get(numeric_column, np.nan), errors="coerce")
    for categorical_column in ["emv_zone_name", "emv_zone_model", "emv_zone_layer", "emv_zone_id", "emv_zone_valid_from"]:
        if categorical_column not in result.columns:
            result[categorical_column] = pd.Series(pd.NA, index=result.index, dtype="object")

    source_path = discovered_sources.get("emv")
    if source_path is None:
        return result, summary

    summary["available"] = True
    summary["source_file"] = os.path.basename(source_path)

    if _get_optional_geopandas() is None:
        summary["reason"] = "geopandas_not_installed"
        return result, summary

    gpkg_path = _resolve_emv_gpkg_path(source_path)
    if gpkg_path is None:
        summary["reason"] = "gpkg_not_found"
        return result, summary

    summary["spatial_enabled"] = True
    summary["gpkg_ready"] = True
    summary["gpkg_file"] = os.path.basename(gpkg_path)

    coordinate_mask = _coordinate_numeric_series(result, "longitude").notna() & _coordinate_numeric_series(
        result, "latitude"
    ).notna()
    summary["rows_with_coordinates"] = int(coordinate_mask.sum())
    if not coordinate_mask.any() or "property_type" not in result.columns:
        return result, summary

    candidate_layer_rows: dict[tuple[str, ...], pd.Index] = {}
    land_types = result.get("vrsta_zemljisca", pd.Series(pd.NA, index=result.index))
    for row_idx in result.index[coordinate_mask & result["emv_zone_match"].isna()]:
        candidate_layers = tuple(_emv_layers_for_row(result.at[row_idx, "property_type"], land_types.at[row_idx]))
        if not candidate_layers:
            continue
        existing_index = candidate_layer_rows.get(candidate_layers)
        if existing_index is None:
            candidate_layer_rows[candidate_layers] = pd.Index([row_idx])
        else:
            candidate_layer_rows[candidate_layers] = existing_index.append(pd.Index([row_idx]))

    for candidate_layers, initial_index in candidate_layer_rows.items():
        row_index = initial_index
        for layer_name in candidate_layers:
            if row_index.empty:
                break

            matches = _match_emv_layer_to_rows(result, row_index, gpkg_path=gpkg_path, layer_name=layer_name)
            if matches.empty:
                continue

            matched_mask = matches.get("ID").notna() if "ID" in matches.columns else pd.Series(False, index=matches.index)
            if not matched_mask.any():
                continue

            matched_index = matches.index[matched_mask]
            result.loc[matched_index, "emv_zone_match"] = 1.0
            if "ST_RAVNI" in matches.columns:
                result.loc[matched_index, "emv_zone_level"] = pd.to_numeric(matches.loc[matched_index, "ST_RAVNI"], errors="coerce")
            if "IME" in matches.columns:
                result.loc[matched_index, "emv_zone_name"] = matches.loc[matched_index, "IME"].astype(str).values
            if "MODEL" in matches.columns:
                result.loc[matched_index, "emv_zone_model"] = matches.loc[matched_index, "MODEL"].astype(str).values
            if "ID" in matches.columns:
                result.loc[matched_index, "emv_zone_id"] = matches.loc[matched_index, "ID"].astype(str).values
            if "DAT_VELJ" in matches.columns:
                result.loc[matched_index, "emv_zone_valid_from"] = matches.loc[matched_index, "DAT_VELJ"].astype(str).values
            result.loc[matched_index, "emv_zone_layer"] = layer_name

            summary["matched_by_layer"][layer_name] = summary["matched_by_layer"].get(layer_name, 0) + int(len(matched_index))
            row_index = row_index[result.loc[row_index, "emv_zone_match"].isna()]

    result["emv_zone_match"] = pd.to_numeric(result["emv_zone_match"], errors="coerce").fillna(0.0)
    summary["rows_with_zone_match"] = int((result["emv_zone_match"] > 0).sum())
    return result, summary


# ── CSV inspection ──────────────────────────────────────────────────


def inspect_csv(csv_path: str, preview_rows: int = 8) -> dict[str, Any]:
    df = read_csv_flexible(csv_path)
    preview = df.head(preview_rows).fillna("").to_dict(orient="records")
    return {
        "row_count": len(df),
        "columns": list(df.columns),
        "preview": preview,
    }


# ── RPE / RN import ────────────────────────────────────────────────


def _read_dbf(dbf_path: str, encoding: str = "cp1250") -> pd.DataFrame:
    """Read a .dbf file into a DataFrame without external dependencies."""
    with open(dbf_path, "rb") as fh:
        data = fh.read()

    num_records = _struct.unpack_from("<I", data, 4)[0]
    header_size = _struct.unpack_from("<H", data, 8)[0]
    record_size = _struct.unpack_from("<H", data, 10)[0]

    fields: list[tuple[str, int]] = []
    pos = 32
    while pos < header_size - 1:
        if data[pos] == 0x0D:
            break
        fname = data[pos : pos + 11].split(b"\x00")[0].decode("ascii")
        fsize = data[pos + 16]
        fields.append((fname, fsize))
        pos += 32

    rows: list[dict[str, str]] = []
    data_start = header_size
    for r in range(num_records):
        rec_offset = data_start + r * record_size
        if rec_offset + record_size > len(data):
            break
        offset = 1  # skip deletion flag
        row: dict[str, str] = {}
        for fname, fsize in fields:
            raw = data[rec_offset + offset : rec_offset + offset + fsize]
            try:
                val = raw.decode(encoding).strip()
            except Exception:
                val = raw.decode("latin1", errors="replace").strip()
            val = val.replace("\x00", "").strip()
            row[fname] = val
            offset += fsize
        rows.append(row)

    return pd.DataFrame(rows)


def _read_dbf_header(fh) -> tuple[int, int, int, list[tuple[str, int]]]:
    header = fh.read(32)
    if len(header) < 32:
        raise ValueError("DBF header is incomplete")

    num_records = _struct.unpack_from("<I", header, 4)[0]
    header_size = _struct.unpack_from("<H", header, 8)[0]
    record_size = _struct.unpack_from("<H", header, 10)[0]

    fields: list[tuple[str, int]] = []
    while fh.tell() < header_size:
      descriptor = fh.read(32)
      if not descriptor:
          break
      if descriptor[0] == 0x0D:
          break
      fname = descriptor[0:11].split(b"\x00")[0].decode("ascii")
      fsize = descriptor[16]
      fields.append((fname, fsize))

    return num_records, header_size, record_size, fields


def inspect_dbf(dbf_path: str, preview_rows: int = 8, encoding: str = "cp1250") -> dict[str, Any]:
    """Inspect a .dbf file without loading the full table into memory."""
    with open(dbf_path, "rb") as fh:
        num_records, header_size, record_size, fields = _read_dbf_header(fh)
        fh.seek(header_size)

        rows: list[dict[str, str]] = []
        preview_limit = max(0, int(preview_rows))
        for _ in range(min(num_records, preview_limit)):
            record = fh.read(record_size)
            if len(record) < record_size:
                break
            offset = 1
            row: dict[str, str] = {}
            for fname, fsize in fields:
                raw = record[offset : offset + fsize]
                try:
                    val = raw.decode(encoding).strip()
                except Exception:
                    val = raw.decode("latin1", errors="replace").strip()
                row[fname] = val.replace("\x00", "").strip()
                offset += fsize
            rows.append(row)

    return {
        "row_count": int(num_records),
        "columns": [fname for fname, _ in fields],
        "rows": rows,
    }


def get_shape_zip_preview_cache_path(zip_path: str) -> str:
    return f"{zip_path}.preview.json"


def load_shape_zip_preview_cache(zip_path: str) -> dict[str, Any] | None:
    cache_path = get_shape_zip_preview_cache_path(zip_path)
    if not os.path.exists(cache_path):
        return None
    with open(cache_path, encoding="utf-8") as fh:
        return json.load(fh)


def save_shape_zip_preview_cache(zip_path: str, preview: dict[str, Any]) -> None:
    cache_path = get_shape_zip_preview_cache_path(zip_path)
    with open(cache_path, "w", encoding="utf-8") as fh:
        json.dump(preview, fh, ensure_ascii=True)


def inspect_shapefile_zip_with_cache(zip_path: str, upload_dir: str, preview_rows: int = 8) -> dict[str, Any]:
    cached = load_shape_zip_preview_cache(zip_path)
    if cached is not None:
        cached_rows = cached.get("rows", [])
        requested_rows = max(0, int(preview_rows))
        return {
            "layers": cached.get("layers", []),
            "columns": cached.get("columns", []),
            "rows": cached_rows[:requested_rows] if requested_rows else [],
            "total_rows": int(cached.get("total_rows", 0)),
        }

    preview = inspect_shapefile_zip(zip_path, upload_dir, preview_rows=max(preview_rows, 50))
    save_shape_zip_preview_cache(zip_path, preview)
    rows: list[dict[str, str]] = []
    return {
        "layers": preview.get("layers", []),
        "columns": preview.get("columns", []),
        "rows": preview.get("rows", [])[: max(0, int(preview_rows))],
        "total_rows": int(preview.get("total_rows", 0)),
    }


def inspect_shapefile_zip(zip_path: str, upload_dir: str, preview_rows: int = 8) -> dict[str, Any]:
    """Inspect a ZIP that contains shapefile components and preview DBF attribute tables."""
    extract_dir = extract_zip_all(zip_path, upload_dir)
    try:
        layers: list[dict[str, Any]] = []
        for root, _, files in os.walk(extract_dir):
            file_lookup = {os.path.splitext(name)[0].lower(): set() for name in files}
            for name in files:
                stem, ext = os.path.splitext(name)
                file_lookup.setdefault(stem.lower(), set()).add(ext.lower())

            for fname in sorted(files):
                if not fname.lower().endswith(".dbf"):
                    continue

                stem = os.path.splitext(fname)[0]
                extensions = file_lookup.get(stem.lower(), set())
                full = os.path.join(root, fname)
                dbf_info = inspect_dbf(full, preview_rows=0)
                layers.append(
                    {
                        "layer_name": stem,
                        "row_count": dbf_info["row_count"],
                        "columns": dbf_info["columns"],
                        "has_geometry": ".shp" in extensions,
                        "has_index": ".shx" in extensions,
                        "has_projection": ".prj" in extensions,
                    }
                )

        if not layers:
            raise ValueError("ZIP does not contain any DBF layers that can be previewed")

        if len(layers) == 1 and preview_rows > 0:
            layer = layers[0]
            dbf_path = None
            for root, _, files in os.walk(extract_dir):
                candidate = f"{layer['layer_name']}.dbf"
                if candidate in files:
                    dbf_path = os.path.join(root, candidate)
                    break
            if dbf_path:
                dbf_preview = inspect_dbf(dbf_path, preview_rows=preview_rows)
                return {
                    "layers": layers,
                    "columns": dbf_preview["columns"],
                    "rows": dbf_preview["rows"],
                    "total_rows": dbf_preview["row_count"],
                }

        summary_rows = [
            {
                "layer_name": layer["layer_name"],
                "row_count": layer["row_count"],
                "columns": ", ".join(layer["columns"][:12]),
                "has_geometry": "yes" if layer["has_geometry"] else "no",
            }
            for layer in layers
        ]
        return {
            "layers": layers,
            "columns": ["layer_name", "row_count", "columns", "has_geometry"],
            "rows": summary_rows,
            "total_rows": len(summary_rows),
        }
    finally:
        shutil.rmtree(extract_dir, ignore_errors=True)


def import_rpe_from_zip(zip_path: str, upload_dir: str) -> dict[str, Any]:
    """Import RPE data from a ZIP with shapefiles (.dbf)."""
    extract_dir = extract_zip_all(zip_path, upload_dir)
    try:
        obcine_dbf = None
        stat_regije_dbf = None
        for root, _, files in os.walk(extract_dir):
            for fname in files:
                if not fname.lower().endswith(".dbf"):
                    continue
                upper = fname.upper()
                full = os.path.join(root, fname)
                if "OBCINE" in upper:
                    obcine_dbf = full
                elif "STATISTICNE_REGIJE" in upper:
                    stat_regije_dbf = full

        if not obcine_dbf:
            raise ValueError("RPE ZIP does not contain an OBCINE .dbf file.")

        obcine_df = _read_dbf(obcine_dbf)
        if "SIFRA" not in obcine_df.columns or "NAZIV" not in obcine_df.columns:
            raise ValueError(f"OBCINE .dbf missing SIFRA/NAZIV columns. Found: {list(obcine_df.columns)}")

        regije_info: list[str] = []
        if stat_regije_dbf:
            sr_df = _read_dbf(stat_regije_dbf)
            if "NAZIV" in sr_df.columns:
                regije_info = sorted(sr_df["NAZIV"].dropna().unique().tolist())

        mappings: list[dict[str, Any]] = []
        for _, row in obcine_df.iterrows():
            sifra = row.get("SIFRA", "")
            naziv = row.get("NAZIV", "")
            if not sifra or not naziv:
                continue
            try:
                sifra_int = int(sifra)
            except (ValueError, TypeError):
                continue
            normalized_name = normalize(naziv)
            regija = FALLBACK_REGIONS.get(normalized_name, "neznana")
            if regija == "neznana":
                for key, val in FALLBACK_REGIONS.items():
                    if key in normalized_name or normalized_name in key:
                        regija = val
                        break
            mappings.append(
                {
                    "obcina_sifra": sifra_int,
                    "obcina_naziv": naziv.strip(),
                    "regija_naziv": regija,
                    "vir": "RPE",
                }
            )

        return {
            "mappings": mappings,
            "count": len(mappings),
            "regije": regije_info or sorted({m["regija_naziv"] for m in mappings if m["regija_naziv"] != "neznana"}),
        }
    finally:
        shutil.rmtree(extract_dir, ignore_errors=True)


def import_rpe_rn(
    rn_csv_path: str,
    stat_regije_csv_path: str | None,
    upload_dir: str,
) -> dict[str, Any]:
    """Import RPE + RN data and build municipality → region mapping."""
    if rn_csv_path.lower().endswith(".zip"):
        return import_rpe_from_zip(rn_csv_path, upload_dir)

    rn_df = read_csv_flexible(rn_csv_path)
    required_rn = ["OBCINA_SIFRA", "OBCINA_NAZIV", "EID_STATISTICNA_REGIJA"]
    missing_rn = [c for c in required_rn if c not in rn_df.columns]
    if missing_rn:
        raise ValueError(f"RN file missing columns: {', '.join(missing_rn)}. Found: {', '.join(rn_df.columns[:20])}")

    eid_to_name: dict[str, str] = {}
    if stat_regije_csv_path:
        sr_df = read_csv_flexible(stat_regije_csv_path)
        eid_col = next((c for c in sr_df.columns if "EID_STATISTICNA_REGIJA" in c.upper()), None)
        naziv_col = next((c for c in sr_df.columns if c.upper() == "NAZIV"), None)
        if eid_col and naziv_col:
            for _, row in sr_df.dropna(subset=[eid_col, naziv_col]).iterrows():
                eid_to_name[str(row[eid_col]).strip()] = str(row[naziv_col]).strip()

    rn_clean = rn_df[required_rn].dropna(subset=required_rn).copy()
    rn_clean["OBCINA_SIFRA"] = pd.to_numeric(rn_clean["OBCINA_SIFRA"], errors="coerce")
    rn_clean = rn_clean.dropna(subset=["OBCINA_SIFRA"])
    rn_clean["OBCINA_SIFRA"] = rn_clean["OBCINA_SIFRA"].astype(int)

    obcina_groups = rn_clean.groupby(["OBCINA_SIFRA", "OBCINA_NAZIV"])["EID_STATISTICNA_REGIJA"].agg(
        lambda x: x.mode().iloc[0] if len(x) > 0 else None
    )

    mappings: list[dict[str, Any]] = []
    for (sifra, naziv), eid_regija in obcina_groups.items():
        regija_naziv = eid_to_name.get(str(eid_regija).strip(), str(eid_regija).strip())
        mappings.append(
            {
                "obcina_sifra": int(sifra),
                "obcina_naziv": str(naziv).strip(),
                "eid_statisticna_regija": str(eid_regija).strip(),
                "regija_naziv": regija_naziv,
                "vir": "RPE/RN",
            }
        )

    return {
        "mappings": mappings,
        "count": len(mappings),
        "regije": sorted({m["regija_naziv"] for m in mappings}),
        "eid_to_name_count": len(eid_to_name),
    }


# ── ETN KPP pairing ────────────────────────────────────────────────


def _enrich_with_sifra(df: pd.DataFrame, merged: pd.DataFrame) -> pd.DataFrame:
    """Add statistical_region using RPE_OBCINE_SIFRA (code) first, then name fallback."""
    result = df.copy()

    if "municipality" in result.columns:
        result["municipality"] = result["municipality"].apply(
            lambda value: format_municipality_label(clean_display_text(value)) or "unknown"
        )
        result["municipality_normalized"] = result["municipality"].apply(normalize_municipality_name)

    # 1. Try RPE_OBCINE_SIFRA (municipality code) — most accurate, unambiguous
    sifra_col = None
    for candidate in ["RPE_OBCINE_SIFRA", "RPE_OBCINE_SIFRA_POSLI"]:
        if candidate in merged.columns:
            sifra_col = candidate
            break

    if sifra_col is not None:
        sifra_vals = merged[sifra_col].reindex(result.index)
        result["statistical_region"] = sifra_vals.apply(lambda v: lookup_region_by_code(v) if pd.notna(v) else None)
    else:
        result["statistical_region"] = None

    # 2. Fallback: RPE_OBCINE_IME (name-based) for rows still missing region
    missing_mask = result["statistical_region"].isna() | (result["statistical_region"] == "neznana")
    if missing_mask.any():
        rpe_ime_col = None
        for candidate in ["RPE_OBCINE_IME", "RPE_OBCINE_IME_POSLI", "IME_OBCINE", "IME_OBCINE_POSLI"]:
            if candidate in merged.columns:
                rpe_ime_col = candidate
                break

        if rpe_ime_col is not None:
            rpe_names = merged[rpe_ime_col].reindex(result.index)
            name_regions = rpe_names.apply(
                lambda v: lookup_region(normalize(str(v))) if pd.notna(v) and str(v).strip() else "neznana"
            )
            result.loc[missing_mask, "statistical_region"] = name_regions[missing_mask]

    # 3. Final fallback: municipality column
    missing_mask = result["statistical_region"].isna() | (result["statistical_region"] == "neznana")
    if missing_mask.any() and "municipality_normalized" in result.columns:
        norm = result.loc[missing_mask, "municipality_normalized"]
        result.loc[missing_mask, "statistical_region"] = norm.apply(lookup_region)

    if "year_built" in result.columns:
        current_year = pd.Timestamp.now().year
        result["building_age"] = current_year - pd.to_numeric(result["year_built"], errors="coerce")
        result["building_age"] = result["building_age"].clip(lower=0)

    if "size_m2" in result.columns:
        result["log_size_m2"] = np.log1p(pd.to_numeric(result["size_m2"], errors="coerce").fillna(0).clip(lower=0))

    return result


def build_training_df_from_etn_kpp(
    posli_df: pd.DataFrame,
    deli_df: pd.DataFrame,
    zemljisca_df: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Core ETN KPP pairing: merge posli + delistavb, extract features, filter."""
    if "ID_POSLA" not in posli_df.columns or "ID_POSLA" not in deli_df.columns:
        raise ValueError("Both ETN files must contain ID_POSLA.")

    required_posli = ["ID_POSLA", "POGODBENA_CENA_ODSKODNINA"]
    for col in required_posli:
        if col not in posli_df.columns:
            raise ValueError(f"Missing required column in posli.csv: {col}")

    candidate_size = ["PRODANA_POVRSINA", "PRODANA_POVRSINA_DELA_STAVBE", "UPORABNA_POVRSINA", "POVRSINA_DELA_STAVBE"]
    size_col = next((c for c in candidate_size if c in deli_df.columns), None)
    if not size_col:
        raise ValueError(f"No area column in delistavb.csv. Expected: {', '.join(candidate_size)}")

    posli_selected = ["ID_POSLA", "POGODBENA_CENA_ODSKODNINA"]
    for opt_col in [
        "TRZNOST_POSLA",
        "RPE_OBCINE_SIFRA",
        "RPE_OBCINE_IME",
        "IME_OBCINE",
        "DATUM_POGODBE",
        "DATUM_SKLENITVE_POGODBE",
        "DATUM_UVELJAVITVE",
        "POGODBENA_CENA_DELA_STAVBE",
        "VRSTA_KUPOPRODAJNEGA_POSLA",
        "VKLJUCENOST_DDV",
        "STOPNJA_DDV",
    ]:
        if opt_col in posli_df.columns:
            posli_selected.append(opt_col)

    merged = deli_df.merge(posli_df[posli_selected], on="ID_POSLA", how="inner", suffixes=("", "_POSLI"))
    if merged.empty:
        raise ValueError("Merging posli.csv and delistavb.csv returned 0 rows.")

    stage_stats: list[dict[str, Any]] = []
    _append_stage(stage_stats, "building_merged_rows", len(merged))

    training_df = pd.DataFrame()
    merged_index = merged.index.to_series(index=merged.index).astype(str)
    part_id_col = next(
        (c for c in ["ID_DELA_STAVBE", "ID_DEL_STAVBE", "ID_STAVBE_DEL", "ID_NEPREMICNINE", "ID_DELA"] if c in merged),
        None,
    )
    training_df["deal_id"] = merged["ID_POSLA"].astype(str)
    if part_id_col is not None:
        training_df["source_row_key"] = merged["ID_POSLA"].astype(str) + ":" + merged[part_id_col].astype(str)
    else:
        training_df["source_row_key"] = merged["ID_POSLA"].astype(str) + ":" + merged_index

    training_df["sifra_ko"] = pd.to_numeric(merged.get("SIFRA_KO", np.nan), errors="coerce")
    training_df["stevilka_stavbe"] = pd.to_numeric(merged.get("STEVILKA_STAVBE", np.nan), errors="coerce")
    training_df["stevilka_dela_stavbe"] = pd.to_numeric(
        merged.get("STEVILKA_DELA_STAVBE", np.nan), errors="coerce"
    )
    training_df["parcelna_stevilka"] = (
        merged["PARCELNA_STEVILKA_ZA_GEOLOKACIJO"].apply(clean_display_text)
        if "PARCELNA_STEVILKA_ZA_GEOLOKACIJO" in merged.columns
        else "unknown"
    )
    training_df["ulica"] = merged["ULICA"].apply(clean_display_text) if "ULICA" in merged.columns else "unknown"
    training_df["hisna_stevilka"] = (
        merged["HISNA_STEVILKA"].apply(clean_display_text) if "HISNA_STEVILKA" in merged.columns else "unknown"
    )
    training_df["dodatek_hs"] = merged["DODATEK_HS"].apply(clean_display_text) if "DODATEK_HS" in merged.columns else "unknown"
    training_df["rpe_obcine_sifra"] = pd.to_numeric(merged.get("RPE_OBCINE_SIFRA", np.nan), errors="coerce")

    training_df["size_m2"] = pd.to_numeric(merged[size_col], errors="coerce")

    # Rooms
    training_df["rooms"] = (
        pd.to_numeric(merged.get("STEVILO_SOB", np.nan), errors="coerce") if "STEVILO_SOB" in merged.columns else np.nan
    )

    # PROSTORI_DELA_STAVBE features
    if "PROSTORI_DELA_STAVBE" in merged.columns:
        prostori_raw = merged["PROSTORI_DELA_STAVBE"].fillna("")
        prostori_lower = prostori_raw.str.lower()
        training_df["num_prostori"] = prostori_raw.str.split(r"\|").apply(
            lambda parts: len([p for p in parts if p.strip()]) if isinstance(parts, list) else 0
        )
        training_df["has_klet"] = prostori_lower.str.contains(r"klet", na=False).astype(int)
        training_df["has_garaza"] = prostori_lower.str.contains(r"gara[zž]", na=False).astype(int)
        training_df["has_terasa"] = prostori_lower.str.contains(r"terasa|balkon|lo[zž]a", na=False).astype(int)
        training_df["has_shramba"] = prostori_lower.str.contains(r"shramba", na=False).astype(int)
    else:
        for col in ["num_prostori", "has_klet", "has_garaza", "has_terasa", "has_shramba"]:
            training_df[col] = 0

    training_df["year_built"] = pd.to_numeric(merged.get("LETO_IZGRADNJE_DELA_STAVBE", np.nan), errors="coerce")
    training_df["floor"] = pd.to_numeric(merged.get("NADSTROPJE_DELA_STAVBE", np.nan), errors="coerce")

    training_df["ime_ko"] = merged["IME_KO"].apply(clean_display_text) if "IME_KO" in merged.columns else "unknown"
    training_df["naselje"] = merged["NASELJE"].apply(clean_display_text) if "NASELJE" in merged.columns else "unknown"
    training_df["vrsta_dela_stavbe"] = (
        merged["VRSTA_DELA_STAVBE"].apply(clean_display_text) if "VRSTA_DELA_STAVBE" in merged.columns else "unknown"
    )
    training_df["evidentiranost_dela_stavbe"] = pd.to_numeric(
        merged.get("EVIDENTIRANOST_DELA_STAVBE", np.nan), errors="coerce"
    )
    training_df["atrij"] = pd.to_numeric(merged.get("ATRIJ", np.nan), errors="coerce")
    training_df["stopnja_ddv"] = pd.to_numeric(merged.get("STOPNJA_DDV", np.nan), errors="coerce")

    # Coordinates (ETRS89/TM)
    if "E_CENTROID" in merged.columns and "N_CENTROID" in merged.columns:
        training_df["longitude"] = pd.to_numeric(merged["E_CENTROID"], errors="coerce")
        training_df["latitude"] = pd.to_numeric(merged["N_CENTROID"], errors="coerce")
    else:
        training_df["latitude"] = np.nan
        training_df["longitude"] = np.nan

    # Novogradnja
    if "NOVOGRADNJA" in merged.columns:
        training_df["novogradnja"] = (
            pd.to_numeric(merged["NOVOGRADNJA"], errors="coerce").fillna(0).clip(0, 1).astype(int)
        )
    else:
        training_df["novogradnja"] = 0

    # Stavba je dokončana
    if "STAVBA_JE_DOKONCANA" in merged.columns:
        training_df["stavba_je_dokoncana"] = (
            pd.to_numeric(merged["STAVBA_JE_DOKONCANA"], errors="coerce").fillna(1).clip(0, 1).astype(int)
        )
    else:
        training_df["stavba_je_dokoncana"] = 1

    # Uporabna površina
    training_df["uporabna_povrsina"] = (
        pd.to_numeric(merged.get("UPORABNA_POVRSINA", np.nan), errors="coerce")
        if "UPORABNA_POVRSINA" in merged.columns
        else np.nan
    )

    training_df["prodani_delez_dela_stavbe"] = _first_numeric_series(
        merged,
        [
            "PRODANI_DELEZ_DELA_STAVBE",
            "PRODAN_DELEZ_DELA_STAVBE",
            "DELEZ_DELA_STAVBE",
        ],
    )

    training_df["gradbena_faza"] = _normalize_gradbena_faza(
        _first_numeric_series(
            merged,
            [
                "GRADBENA_FAZA",
                "GRADBENA_FAZA_DELA_STAVBE",
                "SIFRA_GRADBENE_FAZE",
            ],
        )
    )

    # Lega dela stavbe v stavbi
    if "LEGA_DELA_STAVBE_V_STAVBI" in merged.columns:
        lega_raw = merged["LEGA_DELA_STAVBE_V_STAVBI"].fillna("").astype(str).str.strip().str.lower()

        def _map_lega(val: str) -> str:
            if not val:
                return "unknown"
            if "klet" in val or "suteren" in val:
                return "klet"
            if any(w in val for w in ("nadstropje", "mansarda")):
                return "nadstropje"
            if any(w in val for w in ("pritlicje", "pritličje", "pritlic")):
                return "pritlicje"
            return "unknown"

        training_df["lega_v_stavbi"] = lega_raw.apply(_map_lega)
    else:
        training_df["lega_v_stavbi"] = "unknown"

    # Parking
    if "STEVILO_ZUNANJIH_PARKIRNIH_MEST" in merged.columns:
        training_df["has_parking"] = (
            pd.to_numeric(merged["STEVILO_ZUNANJIH_PARKIRNIH_MEST"], errors="coerce")
            .fillna(0)
            .clip(lower=0)
            .gt(0)
            .astype(int)
        )
    else:
        training_df["has_parking"] = 0

    # DDV
    vkljucenost_col = next((c for c in ["VKLJUCENOST_DDV", "VKLJUCENOST_DDV_POSLI"] if c in merged.columns), None)
    if vkljucenost_col is not None:
        training_df["ddv_vkljucen"] = (
            pd.to_numeric(merged[vkljucenost_col], errors="coerce").fillna(0).clip(0, 1).astype(int)
        )
    else:
        training_df["ddv_vkljucen"] = 0

    # Transaction date → extract quarter for seasonality
    date_col = next(
        (
            c
            for c in [
                "DATUM_SKLENITVE_POGODBE",
                "DATUM_UVELJAVITVE",
                "DATUM_POGODBE",
                "DATUM_SKLENITVE_POGODBE_POSLI",
                "DATUM_UVELJAVITVE_POSLI",
                "DATUM_POGODBE_POSLI",
            ]
            if c in merged.columns
        ),
        None,
    )
    if date_col is not None:
        date_parsed = pd.to_datetime(merged[date_col], errors="coerce", dayfirst=True)
        training_df["transaction_quarter"] = date_parsed.dt.quarter.astype("float64")
    else:
        training_df["transaction_quarter"] = np.nan

    # Municipality
    municipality_source = None
    municipality_series = None
    for muni_candidate in [
        "OBCINA",
        "IME_OBCINE",
        "RPE_OBCINE_IME",
        "OBCINA_POSLI",
        "IME_OBCINE_POSLI",
        "RPE_OBCINE_IME_POSLI",
    ]:
        if muni_candidate in merged.columns:
            candidate_series = merged[muni_candidate].astype(str).str.strip()
            if (candidate_series != "").mean() > 0:
                municipality_source = muni_candidate
                municipality_series = candidate_series
                break
    if municipality_series is not None:
        training_df["municipality"] = municipality_series.apply(
            lambda value: format_municipality_label(clean_display_text(value)) or "unknown"
        )
    else:
        training_df["municipality"] = "unknown"

    # Property type
    property_type_source = None
    for type_candidate in ["DEJANSKA_RABA_DELA_STAVBE", "VRSTA_DELA_STAVBE"]:
        if type_candidate in merged.columns:
            property_type_source = type_candidate
            break
    training_df["property_type"] = (
        merged[property_type_source].apply(group_property_type) if property_type_source else "ostalo"
    )

    # Price: pro-rate total transaction price by area share
    total_price = pd.to_numeric(merged["POGODBENA_CENA_ODSKODNINA"], errors="coerce")
    per_unit_price = None
    for per_unit_col in ["POGODBENA_CENA_DELA_STAVBE"]:
        for candidate in [per_unit_col, f"{per_unit_col}_POSLI"]:
            if candidate in merged.columns:
                per_unit_price = pd.to_numeric(merged[candidate], errors="coerce")
                break
        if per_unit_price is not None:
            break

    merged["_area_numeric"] = pd.to_numeric(merged[size_col], errors="coerce").fillna(0)
    total_area_per_deal = merged.groupby("ID_POSLA")["_area_numeric"].transform("sum")
    area_ratio = merged["_area_numeric"] / total_area_per_deal.replace(0, np.nan)
    prorated_price = total_price * area_ratio

    if per_unit_price is not None:
        has_unit_price = per_unit_price.notna() & (per_unit_price > 0)
        training_df["price_eur"] = prorated_price.copy()
        training_df.loc[has_unit_price, "price_eur"] = per_unit_price[has_unit_price]
    else:
        training_df["price_eur"] = prorated_price

    training_df = training_df.dropna(subset=["size_m2", "price_eur"])
    training_df = training_df[(training_df["size_m2"] > 0) & (training_df["price_eur"] > 0)]
    _append_stage(stage_stats, "building_after_price_size_presence", len(training_df))

    # TRZNOST_POSLA: keep only market transactions (1=market, 2=market/poor quality, 5=under review)
    if "TRZNOST_POSLA" in merged.columns:
        trznost = pd.to_numeric(merged["TRZNOST_POSLA"], errors="coerce")
        trznost_aligned = trznost.reindex(training_df.index)
        training_df = training_df.loc[trznost_aligned.isin([1, 2, 5])].copy()
    _append_stage(stage_stats, "building_after_market_filter", len(training_df))

    # VRSTA_KUPOPRODAJNEGA_POSLA: keep only open market (1) and voluntary auction (2)
    vrsta_posla_col = next(
        (c for c in ["VRSTA_KUPOPRODAJNEGA_POSLA", "VRSTA_KUPOPRODAJNEGA_POSLA_POSLI"] if c in merged.columns), None
    )
    training_df["vrsta_kupoprodajnega_posla"] = (
        merged[vrsta_posla_col].astype(str).str.strip() if vrsta_posla_col is not None else "unknown"
    )
    if vrsta_posla_col is not None:
        vrsta_posla = pd.to_numeric(merged[vrsta_posla_col], errors="coerce")
        vrsta_aligned = vrsta_posla.reindex(training_df.index)
        training_df = training_df.loc[vrsta_aligned.isin([1, 2]) | vrsta_aligned.isna()].copy()
    _append_stage(stage_stats, "building_after_sale_type_filter", len(training_df))

    # Exclude non-market types
    training_df = training_df[~training_df["property_type"].isin(EXCLUDED_PROPERTY_TYPES)].copy()
    _append_stage(stage_stats, "building_after_excluded_property_types", len(training_df))

    # Outlier removal
    price_per_m2 = training_df["price_eur"] / training_df["size_m2"]
    training_df = training_df[
        (training_df["price_eur"] <= 2_000_000)
        & (price_per_m2 <= 15_000)
        & (training_df["size_m2"] <= 1000)
        & (training_df["size_m2"] >= 5)
    ].copy()
    _append_stage(stage_stats, "building_after_basic_outlier_filters", len(training_df))

    # Remove symbolic/absurd transactions
    if len(training_df) > 0:
        price_floor = max(1_000.0, training_df["price_eur"].quantile(0.005))
        training_df = training_df[training_df["price_eur"] >= price_floor].copy()
        _append_stage(stage_stats, "building_after_price_floor", len(training_df))
        ppm2 = training_df["price_eur"] / training_df["size_m2"]
        ppm2_ceil = ppm2.quantile(0.999)
        training_df = training_df[ppm2 <= ppm2_ceil].copy()
        _append_stage(stage_stats, "building_after_ppm2_cap", len(training_df))
    else:
        _append_stage(stage_stats, "building_after_price_floor", len(training_df))
        _append_stage(stage_stats, "building_after_ppm2_cap", len(training_df))

    training_df["property_type"] = training_df["property_type"].apply(normalize_text)

    # Enrich
    training_df = _enrich_with_sifra(training_df, merged)
    _append_stage(stage_stats, "building_after_enrichment", len(training_df))

    # Land area from ZEMLJISCA
    if zemljisca_df is not None and "ID_POSLA" in zemljisca_df.columns and "POVRSINA_PARCELE" in zemljisca_df.columns:
        z_agg = zemljisca_df.groupby("ID_POSLA")["POVRSINA_PARCELE"].sum().reset_index()
        z_agg.columns = ["ID_POSLA", "parcela_m2"]
        z_agg["parcela_m2"] = pd.to_numeric(z_agg["parcela_m2"], errors="coerce")
        id_posla_aligned = merged["ID_POSLA"].reindex(training_df.index)
        training_df["parcela_m2"] = id_posla_aligned.map(z_agg.set_index("ID_POSLA")["parcela_m2"])
    else:
        training_df["parcela_m2"] = np.nan

    if zemljisca_df is not None and "ID_POSLA" in zemljisca_df.columns:
        if "VRSTA_ZEMLJISCA" in zemljisca_df.columns:
            land_type_by_deal = zemljisca_df.groupby("ID_POSLA")["VRSTA_ZEMLJISCA"].agg(
                lambda values: (
                    clean_display_text(values.dropna().astype(str).mode().iloc[0])
                    if len(values.dropna())
                    else "unknown"
                )
            )
            id_posla_aligned = merged["ID_POSLA"].reindex(training_df.index)
            training_df["vrsta_zemljisca"] = id_posla_aligned.map(land_type_by_deal).fillna("unknown")
        else:
            training_df["vrsta_zemljisca"] = "unknown"

        parcel_share_col = next(
            (
                c
                for c in [
                    "PRODANI_DELEZ_PARCELE",
                    "PRODAN_DELEZ_PARCELE",
                    "DELEZ_PARCELE",
                ]
                if c in zemljisca_df.columns
            ),
            None,
        )
        if parcel_share_col is not None:
            parcel_share_df = zemljisca_df[["ID_POSLA", parcel_share_col]].copy()
            parcel_share_df["parcel_share"] = _parse_fractional_numeric_series(parcel_share_df[parcel_share_col])

            if "POVRSINA_PARCELE" in zemljisca_df.columns:
                parcel_share_df["parcel_area"] = pd.to_numeric(zemljisca_df["POVRSINA_PARCELE"], errors="coerce")
                valid = parcel_share_df["parcel_share"].notna() & parcel_share_df["parcel_area"].notna()
                weighted_sum = parcel_share_df.loc[valid, "parcel_share"] * parcel_share_df.loc[valid, "parcel_area"]
                weight_sum = parcel_share_df.loc[valid].groupby("ID_POSLA")["parcel_area"].sum()
                share_by_deal = weighted_sum.groupby(parcel_share_df.loc[valid, "ID_POSLA"]).sum() / weight_sum
            else:
                share_by_deal = parcel_share_df.groupby("ID_POSLA")["parcel_share"].mean()

            id_posla_aligned = merged["ID_POSLA"].reindex(training_df.index)
            training_df["prodani_delez_parcele"] = id_posla_aligned.map(share_by_deal)
        else:
            training_df["prodani_delez_parcele"] = np.nan
    else:
        training_df["vrsta_zemljisca"] = "unknown"
        training_df["prodani_delez_parcele"] = np.nan

    if training_df.empty:
        raise ValueError("No valid rows after filtering ETN data.")

    _append_stage(stage_stats, "building_final_rows", len(training_df))

    meta = {
        "used_size_column": size_col,
        "used_property_type_column": property_type_source,
        "used_municipality_column": municipality_source,
        "filter_stats": {
            "inputs": {
                "posli_rows": int(len(posli_df)),
                "delistavb_rows": int(len(deli_df)),
                "zemljisca_rows": int(len(zemljisca_df)) if zemljisca_df is not None else 0,
            },
            "stages": stage_stats,
        },
    }
    return training_df, meta


def build_training_df_from_etn_kpp_land(
    posli_df: pd.DataFrame,
    zemljisca_df: pd.DataFrame,
    *,
    exclude_posli_ids: set[str] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Build parcela rows from land-only ETN transactions."""
    if "ID_POSLA" not in posli_df.columns or "ID_POSLA" not in zemljisca_df.columns:
        raise ValueError("Both ETN files must contain ID_POSLA.")

    if "POVRSINA_PARCELE" not in zemljisca_df.columns:
        raise ValueError("zemljisca.csv missing POVRSINA_PARCELE")

    land_df = zemljisca_df.copy()
    if exclude_posli_ids:
        land_df = land_df[~land_df["ID_POSLA"].astype(str).isin(exclude_posli_ids)].copy()
    if land_df.empty:
        raise ValueError("No land-only transactions after excluding building deals.")

    stage_stats: list[dict[str, Any]] = []
    _append_stage(stage_stats, "land_candidates_after_building_exclusion", len(land_df))

    posli_selected = ["ID_POSLA", "POGODBENA_CENA_ODSKODNINA"]
    for opt_col in [
        "TRZNOST_POSLA",
        "RPE_OBCINE_SIFRA",
        "RPE_OBCINE_IME",
        "IME_OBCINE",
        "VRSTA_KUPOPRODAJNEGA_POSLA",
        "VKLJUCENOST_DDV",
        "STOPNJA_DDV",
        "DATUM_SKLENITVE_POGODBE",
        "DATUM_UVELJAVITVE",
    ]:
        if opt_col in posli_df.columns:
            posli_selected.append(opt_col)

    merged = land_df.merge(posli_df[posli_selected], on="ID_POSLA", how="inner", suffixes=("", "_POSLI"))
    if merged.empty:
        raise ValueError("Merging posli.csv and zemljisca.csv returned 0 rows.")
    _append_stage(stage_stats, "land_merged_rows", len(merged))

    training_df = pd.DataFrame()
    merged_index = merged.index.to_series(index=merged.index).astype(str)
    parcel_id_col = next((c for c in ["PARCELNA_STEVILKA", "FEATUREID"] if c in merged.columns), None)
    training_df["deal_id"] = merged["ID_POSLA"].astype(str)
    if parcel_id_col is not None:
        training_df["source_row_key"] = merged["ID_POSLA"].astype(str) + ":land:" + merged[parcel_id_col].astype(str)
    else:
        training_df["source_row_key"] = merged["ID_POSLA"].astype(str) + ":land:" + merged_index

    training_df["sifra_ko"] = pd.to_numeric(merged.get("SIFRA_KO", np.nan), errors="coerce")
    training_df["stevilka_stavbe"] = np.nan
    training_df["stevilka_dela_stavbe"] = np.nan
    training_df["parcelna_stevilka"] = (
        merged["PARCELNA_STEVILKA"].apply(clean_display_text) if "PARCELNA_STEVILKA" in merged.columns else "unknown"
    )
    training_df["ulica"] = "unknown"
    training_df["hisna_stevilka"] = "unknown"
    training_df["dodatek_hs"] = "unknown"
    training_df["rpe_obcine_sifra"] = pd.to_numeric(merged.get("RPE_OBCINE_SIFRA", np.nan), errors="coerce")

    training_df["size_m2"] = pd.to_numeric(merged["POVRSINA_PARCELE"], errors="coerce")
    training_df["rooms"] = np.nan
    training_df["num_prostori"] = 0
    training_df["has_klet"] = 0
    training_df["has_garaza"] = 0
    training_df["has_terasa"] = 0
    training_df["has_shramba"] = 0
    training_df["year_built"] = np.nan
    training_df["floor"] = np.nan
    training_df["ime_ko"] = merged["IME_KO"].apply(clean_display_text) if "IME_KO" in merged.columns else "unknown"
    training_df["naselje"] = "unknown"
    training_df["vrsta_dela_stavbe"] = "unknown"
    training_df["evidentiranost_dela_stavbe"] = np.nan
    training_df["atrij"] = np.nan
    training_df["stopnja_ddv"] = pd.to_numeric(
        merged.get("STOPNJA_DDV_PARCELE", merged.get("STOPNJA_DDV", np.nan)),
        errors="coerce",
    )
    training_df["longitude"] = pd.to_numeric(merged.get("E_CENTROID", np.nan), errors="coerce")
    training_df["latitude"] = pd.to_numeric(merged.get("N_CENTROID", np.nan), errors="coerce")
    training_df["novogradnja"] = 0
    training_df["stavba_je_dokoncana"] = np.nan
    training_df["uporabna_povrsina"] = np.nan
    training_df["prodani_delez_dela_stavbe"] = np.nan
    training_df["gradbena_faza"] = np.nan
    training_df["lega_v_stavbi"] = "unknown"
    training_df["has_parking"] = 0

    vkljucenost_col = next((c for c in ["VKLJUCENOST_DDV", "VKLJUCENOST_DDV_POSLI"] if c in merged.columns), None)
    if vkljucenost_col is not None:
        training_df["ddv_vkljucen"] = (
            pd.to_numeric(merged[vkljucenost_col], errors="coerce").fillna(0).clip(0, 1).astype(int)
        )
    else:
        training_df["ddv_vkljucen"] = 0

    # Transaction date → extract quarter for seasonality
    land_date_col = next(
        (
            c
            for c in [
                "DATUM_SKLENITVE_POGODBE",
                "DATUM_UVELJAVITVE",
                "DATUM_SKLENITVE_POGODBE_POSLI",
                "DATUM_UVELJAVITVE_POSLI",
            ]
            if c in merged.columns
        ),
        None,
    )
    if land_date_col is not None:
        land_date_parsed = pd.to_datetime(merged[land_date_col], errors="coerce", dayfirst=True)
        training_df["transaction_quarter"] = land_date_parsed.dt.quarter.astype("float64")
    else:
        training_df["transaction_quarter"] = np.nan

    municipality_series = None
    for muni_candidate in ["OBCINA", "IME_OBCINE", "RPE_OBCINE_IME", "OBCINA_POSLI", "IME_OBCINE_POSLI"]:
        if muni_candidate in merged.columns:
            candidate_series = merged[muni_candidate].astype(str).str.strip()
            if (candidate_series != "").mean() > 0:
                municipality_series = candidate_series
                break
    if municipality_series is not None:
        training_df["municipality"] = municipality_series.apply(
            lambda value: format_municipality_label(clean_display_text(value)) or "unknown"
        )
    else:
        training_df["municipality"] = "unknown"

    training_df["property_type"] = "parcela"
    vrsta_posla_col = next(
        (c for c in ["VRSTA_KUPOPRODAJNEGA_POSLA", "VRSTA_KUPOPRODAJNEGA_POSLA_POSLI"] if c in merged.columns), None
    )
    training_df["vrsta_kupoprodajnega_posla"] = (
        merged[vrsta_posla_col].astype(str).str.strip() if vrsta_posla_col is not None else "unknown"
    )
    training_df["parcela_m2"] = training_df["size_m2"]
    training_df["vrsta_zemljisca"] = (
        merged["VRSTA_ZEMLJISCA"].apply(clean_display_text) if "VRSTA_ZEMLJISCA" in merged.columns else "unknown"
    )
    training_df["prodani_delez_parcele"] = _parse_fractional_numeric_series(
        merged.get("PRODANI_DELEZ_PARCELE", pd.Series(np.nan, index=merged.index))
    )

    parcel_component_price = pd.to_numeric(merged.get("POGODBENA_CENA_PARCELE", np.nan), errors="coerce")
    total_price = pd.to_numeric(merged["POGODBENA_CENA_ODSKODNINA"], errors="coerce")
    total_area_per_deal = training_df.groupby("deal_id")["size_m2"].transform("sum")
    area_ratio = training_df["size_m2"] / total_area_per_deal.replace(0, np.nan)
    prorated_price = total_price * area_ratio
    training_df["price_eur"] = parcel_component_price
    training_df.loc[training_df["price_eur"].isna() | (training_df["price_eur"] <= 0), "price_eur"] = prorated_price

    training_df = training_df.dropna(subset=["size_m2", "price_eur"])
    training_df = training_df[(training_df["size_m2"] > 0) & (training_df["price_eur"] > 0)]
    _append_stage(stage_stats, "land_after_price_size_presence", len(training_df))

    if "TRZNOST_POSLA" in merged.columns:
        trznost = pd.to_numeric(merged["TRZNOST_POSLA"], errors="coerce")
        trznost_aligned = trznost.reindex(training_df.index)
        training_df = training_df.loc[trznost_aligned.isin([1, 2, 5])].copy()
    _append_stage(stage_stats, "land_after_market_filter", len(training_df))

    if vrsta_posla_col is not None:
        vrsta_posla = pd.to_numeric(merged[vrsta_posla_col], errors="coerce")
        vrsta_aligned = vrsta_posla.reindex(training_df.index)
        training_df = training_df.loc[vrsta_aligned.isin([1, 2]) | vrsta_aligned.isna()].copy()
    _append_stage(stage_stats, "land_after_sale_type_filter", len(training_df))

    price_per_m2 = training_df["price_eur"] / training_df["size_m2"]
    training_df = training_df[
        (training_df["price_eur"] <= 2_000_000)
        & (price_per_m2 <= 15_000)
        & (training_df["size_m2"] <= 200_000)
        & (training_df["size_m2"] >= 5)
    ].copy()
    _append_stage(stage_stats, "land_after_basic_outlier_filters", len(training_df))

    if len(training_df) > 0:
        price_floor = max(1_000.0, training_df["price_eur"].quantile(0.005))
        training_df = training_df[training_df["price_eur"] >= price_floor].copy()
    _append_stage(stage_stats, "land_after_price_floor", len(training_df))

    training_df = _enrich_with_sifra(training_df, merged)
    _append_stage(stage_stats, "land_final_rows", len(training_df))
    if training_df.empty:
        raise ValueError("No valid land-only ETN rows after filtering.")

    return training_df, {
        "used_size_column": "POVRSINA_PARCELE",
        "used_property_type_column": "land_only",
        "used_municipality_column": "OBCINA",
        "filter_stats": {
            "inputs": {
                "posli_rows": int(len(posli_df)),
                "zemljisca_rows": int(len(zemljisca_df)),
                "excluded_posli_ids": int(len(exclude_posli_ids or set())),
            },
            "stages": stage_stats,
        },
    }


def prepare_training_csv_from_etn_kpp(
    posli_csv_path: str,
    delistavb_csv_path: str,
    output_csv_path: str,
    enrichment_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Prepare training CSV from ETN KPP posli + delistavb pair."""
    posli_df = read_csv_flexible(posli_csv_path)
    deli_df = read_csv_flexible(delistavb_csv_path)
    training_df, meta = build_training_df_from_etn_kpp(posli_df, deli_df)
    training_df, enrichment_summary = apply_gurs_deterministic_enrichment(
        training_df,
        upload_dir=os.path.dirname(posli_csv_path),
        enrichment_options=enrichment_options,
    )
    resolved_options = resolve_enrichment_options(enrichment_options)

    os.makedirs(os.path.dirname(output_csv_path), exist_ok=True)
    training_df.to_csv(output_csv_path, index=False)
    _write_training_metadata(
        output_csv_path,
        {
            "source": "etn_kpp",
            "rows": len(training_df),
            "columns": list(training_df.columns),
            "reports": [
                {
                    "label": "single",
                    "status": "ok",
                    "rows": len(training_df),
                    **meta,
                    "enrichment_summary": enrichment_summary,
                }
            ],
            "filter_summary": {
                "building": _aggregate_stage_sequences([meta.get("filter_stats", {}).get("stages", [])]),
                "land": [],
            },
            "enrichment_summary": enrichment_summary,
            "enrichment_options": resolved_options,
        },
    )

    return {
        "output_csv_path": output_csv_path,
        "rows": len(training_df),
        "columns": list(training_df.columns),
        "source": "etn_kpp",
        "enrichment_summary": enrichment_summary,
        "enrichment_options": resolved_options,
        **meta,
    }


def _append_prepared_frame_csv(
    frame: pd.DataFrame,
    csv_path: str,
    expected_columns: list[str],
    *,
    write_header: bool,
) -> int:
    prepared = frame.reindex(columns=expected_columns, fill_value=pd.NA)
    prepared.to_csv(csv_path, mode="a", header=write_header, index=False)
    return len(prepared)


def _merge_staged_prepared_frames(
    staged_csv_paths: list[str],
    output_csv_path: str,
) -> tuple[list[str], int, int, dict[str, int]]:
    if not staged_csv_paths:
        raise ValueError("No staged training frames available.")

    discovered_columns: list[str] = []
    discovered_set: set[str] = set()
    dedupe_columns: list[str] = []
    dedupe_keys_seen: set[tuple[Any, ...]] = set()
    rows_before_dedup = 0
    rows_written = 0
    per_year: dict[str, int] = {}

    for staged_csv_path in staged_csv_paths:
        header = pd.read_csv(staged_csv_path, nrows=0)
        for column in header.columns.tolist():
            if column not in discovered_set:
                discovered_set.add(column)
                discovered_columns.append(column)

    dedupe_columns = [col for col in ["source_label", "source_row_key"] if col in discovered_set]

    if os.path.exists(output_csv_path):
        os.remove(output_csv_path)

    write_header = True
    for staged_csv_path in staged_csv_paths:
        frame = pd.read_csv(staged_csv_path)
        rows_before_dedup += len(frame)

        if dedupe_columns:
            if any(column not in frame.columns for column in dedupe_columns):
                keep_mask = pd.Series(True, index=frame.index)
            else:
                keep_rows: list[bool] = []
                dedupe_values = frame[dedupe_columns].itertuples(index=False, name=None)
                for key in dedupe_values:
                    if key in dedupe_keys_seen:
                        keep_rows.append(False)
                        continue
                    dedupe_keys_seen.add(key)
                    keep_rows.append(True)
                keep_mask = pd.Series(keep_rows, index=frame.index)
            frame = frame.loc[keep_mask].copy()

        if frame.empty:
            continue

        if "source_label" in frame.columns:
            counts = frame.groupby("source_label", dropna=False).size()
            for label, count in counts.items():
                per_year[str(label)] = per_year.get(str(label), 0) + int(count)

        rows_written += _append_prepared_frame_csv(
            frame,
            output_csv_path,
            discovered_columns,
            write_header=write_header,
        )
        write_header = False

    if rows_written == 0:
        raise ValueError("No valid ETN pairs produced training data.")

    return discovered_columns, rows_before_dedup, rows_written, dict(sorted(per_year.items()))


def prepare_training_csv_from_etn_kpp_bulk(
    pairs: list[dict[str, Any]],
    output_csv_path: str,
    status_callback: Callable[..., None] | None = None,
    enrichment_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Prepare training CSV from multiple ETN KPP pairs (multi-year)."""
    if not pairs:
        raise ValueError("No ETN pairs provided.")

    reports: list[dict[str, Any]] = []
    resolved_options = resolve_enrichment_options(enrichment_options)
    pairs_used = 0
    total_pairs = len(pairs)
    total_units = max(total_pairs * 4 + 2, 1)

    def emit_status(unit: int, stage: str, **extra: Any) -> None:
        if status_callback is None:
            return
        progress = min(99, max(0, int(round((unit / total_units) * 100))))
        status_callback(
            stage=stage,
            progress=progress,
            total_pairs=total_pairs,
            pairs_completed=pairs_used,
            **extra,
        )

    os.makedirs(os.path.dirname(output_csv_path), exist_ok=True)
    emit_status(0, "initializing")

    with tempfile.TemporaryDirectory(prefix="prepared_etn_bulk_") as staging_dir:
        staged_csv_paths: list[str] = []

        for pair_index, pair in enumerate(pairs):
            posli_csv_path = pair.get("posli_csv_path")
            delistavb_csv_path = pair.get("delistavb_csv_path")
            zemljisca_csv_path = pair.get("zemljisca_csv_path")
            label = str(pair.get("label") or pair.get("year") or "unknown")

            if not posli_csv_path or not delistavb_csv_path:
                reports.append({"label": label, "status": "skipped", "reason": "missing paths"})
                continue

            pair_unit = pair_index * 4
            emit_status(
                pair_unit + 1,
                "loading_pair",
                current_label=label,
                current_pair_index=pair_index + 1,
            )

            posli_df = read_csv_flexible(posli_csv_path)
            deli_df = read_csv_flexible(delistavb_csv_path)
            zemljisca_df = None
            if zemljisca_csv_path:
                with contextlib.suppress(Exception):
                    zemljisca_df = read_csv_flexible(zemljisca_csv_path)

            try:
                pair_staged_paths: list[str] = []
                emit_status(
                    pair_unit + 2,
                    "building_rows",
                    current_label=label,
                    current_pair_index=pair_index + 1,
                )
                frame, meta = build_training_df_from_etn_kpp(posli_df, deli_df, zemljisca_df)
                emit_status(
                    pair_unit + 3,
                    "enriching_buildings",
                    current_label=label,
                    current_pair_index=pair_index + 1,
                    building_rows=len(frame),
                )
                frame, enrichment_summary = apply_gurs_deterministic_enrichment(
                    frame,
                    upload_dir=os.path.dirname(posli_csv_path),
                    enrichment_options=resolved_options,
                )
                frame["source_label"] = label
                frame["transaction_year"] = pd.to_numeric(label, errors="coerce")
                building_stage_path = os.path.join(staging_dir, f"{pair_index}_building.csv")
                frame.to_csv(building_stage_path, index=False)
                pair_staged_paths.append(building_stage_path)

                report = {
                    "label": label,
                    "status": "ok",
                    "rows": len(frame),
                    **meta,
                    "enrichment_summary": enrichment_summary,
                    "enrichment_options": resolved_options,
                    "building_filter_stats": meta.get("filter_stats", {}).get("stages", []),
                }

                if zemljisca_df is not None:
                    emit_status(
                        pair_unit + 4,
                        "enriching_land",
                        current_label=label,
                        current_pair_index=pair_index + 1,
                    )
                    land_only_ids = set(deli_df["ID_POSLA"].astype(str)) if "ID_POSLA" in deli_df.columns else set()
                    with contextlib.suppress(Exception):
                        land_frame, land_meta = build_training_df_from_etn_kpp_land(
                            posli_df,
                            zemljisca_df,
                            exclude_posli_ids=land_only_ids,
                        )
                        land_frame, land_enrichment_summary = apply_gurs_deterministic_enrichment(
                            land_frame,
                            upload_dir=os.path.dirname(posli_csv_path),
                            enrichment_options=resolved_options,
                        )
                        land_frame["source_label"] = label
                        land_frame["transaction_year"] = pd.to_numeric(label, errors="coerce")
                        land_stage_path = os.path.join(staging_dir, f"{pair_index}_land.csv")
                        land_frame.to_csv(land_stage_path, index=False)
                        pair_staged_paths.append(land_stage_path)
                        report["parcel_rows"] = len(land_frame)
                        report["rows"] += len(land_frame)
                        report["land_filter_stats"] = land_meta.get("filter_stats", {}).get("stages", [])
                        report["land_enrichment_summary"] = land_enrichment_summary
                else:
                    emit_status(
                        pair_unit + 4,
                        "finalizing_pair",
                        current_label=label,
                        current_pair_index=pair_index + 1,
                    )

                staged_csv_paths.extend(pair_staged_paths)
                pairs_used += 1
                reports.append(report)
            except Exception as exc:
                reports.append({"label": label, "status": "error", "reason": str(exc)})

        if not staged_csv_paths:
            raise ValueError("No valid ETN pairs produced training data.")

        emit_status(total_units - 1, "merging_outputs", staged_files=len(staged_csv_paths))
        columns, rows_before_dedup, rows_after_dedup, per_year = _merge_staged_prepared_frames(
            staged_csv_paths,
            output_csv_path,
        )
        deduplicated_rows = rows_before_dedup - rows_after_dedup

        filter_summary = {
            "building": _aggregate_stage_sequences(
                [report.get("building_filter_stats", []) for report in reports if report.get("building_filter_stats")]
            ),
            "land": _aggregate_stage_sequences(
                [report.get("land_filter_stats", []) for report in reports if report.get("land_filter_stats")]
            ),
        }
        _write_training_metadata(
            output_csv_path,
            {
                "source": "etn_kpp_bulk",
                "rows": rows_after_dedup,
                "columns": columns,
                "pairs_received": len(pairs),
                "pairs_used": pairs_used,
                "deduplicated_rows": deduplicated_rows,
                "per_year": per_year,
                "reports": reports,
                "enrichment_options": resolved_options,
                "filter_summary": filter_summary,
                "enrichment_summary": {
                    "years": {
                        str(report.get("label")): report.get("enrichment_summary", {})
                        for report in reports
                        if report.get("status") == "ok"
                    }
                },
            },
        )

    if status_callback is not None:
        status_callback(
            stage="completed",
            progress=100,
            total_pairs=total_pairs,
            pairs_completed=pairs_used,
            rows=rows_after_dedup,
            per_year=per_year,
        )

    return {
        "output_csv_path": output_csv_path,
        "rows": rows_after_dedup,
        "columns": columns,
        "source": "etn_kpp_bulk",
        "pairs_received": len(pairs),
        "pairs_used": pairs_used,
        "deduplicated_rows": deduplicated_rows,
        "per_year": per_year,
        "enrichment_options": resolved_options,
        "filter_summary": filter_summary,
        "enrichment_summary": {
            "years": {
                str(report.get("label")): report.get("enrichment_summary", {})
                for report in reports
                if report.get("status") == "ok"
            }
        },
        "reports": reports,
    }
