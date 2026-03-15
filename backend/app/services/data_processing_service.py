"""Data processing service — ETN CSV parsing, feature extraction, training data preparation."""

from __future__ import annotations

import hashlib
import os
import unicodedata
import uuid
from typing import Any

import numpy as np
import pandas as pd

from app.services.regions_service import lookup_region

# Property type mapping from VRSTA_DELA_STAVBE codes
_PROPERTY_TYPE_MAP = {
    1: "hisa", 2: "stanovanje", 3: "stanovanje", 4: "poslovni_prostor",
    5: "poslovni_prostor", 6: "industrijski", 7: "industrijski", 8: "industrijski",
    9: "poslovni_prostor", 10: "turisticni", 11: "gostinstvo", 12: "gostinstvo",
    13: "klet_shramba", 14: "klet_shramba", 15: "garaza", 16: "garaza",
    17: "kmetijsko", 18: "kmetijsko", 19: "kmetijsko", 20: "kmetijsko",
    21: "industrijski", 22: "poslovni_prostor", 23: "poslovni_prostor",
    24: "poslovni_prostor", 25: "poslovni_prostor", 26: "poslovni_prostor",
    27: "kmetijsko", 28: "kmetijsko", 29: "kmetijsko", 30: "poslovni_prostor",
    31: "poslovni_prostor", 32: "poslovni_prostor", 33: "klet_shramba",
    34: "klet_shramba", 35: "ostalo", 36: "ostalo", 37: "ostalo", 38: "ostalo",
    39: "ostalo", 40: "stanovanje", 41: "stanovanje", 42: "hisa", 43: "hisa",
    44: "hisa", 45: "hisa", 46: "hisa", 47: "stanovanje", 48: "stanovanje",
    49: "stanovanje", 50: "poslovni_prostor", 51: "industrijski",
    52: "industrijski", 53: "poslovni_prostor", 54: "turisticni", 55: "turisticni",
    56: "gostinstvo", 57: "klet_shramba", 58: "garaza", 59: "garaza", 60: "hisa",
    61: "kmetijsko", 62: "kmetijsko",
}

_CC_SI_PREFIX_MAP = {
    "1110": "hisa", "1121": "hisa", "1122": "stanovanje", "1130": "stanovanje",
    "1211": "gostinstvo", "1212": "turisticni", "1220": "poslovni_prostor",
    "1230": "poslovni_prostor", "1242": "garaza", "1251": "industrijski",
    "1252": "industrijski", "1261": "poslovni_prostor", "1271": "kmetijsko",
    "1274": "klet_shramba",
}

EXCLUDED_PROPERTY_TYPES = {"ostalo", "klet_shramba"}


def normalize_text(value: Any) -> str:
    if pd.isna(value):
        return "unknown"
    text = str(value).strip()
    if not text:
        return "unknown"
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.split()).lower() or "unknown"


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


def read_csv_flexible(csv_path: str) -> pd.DataFrame:
    for encoding in ["utf-8", "cp1250", "latin1"]:
        for sep in [",", ";", "\t"]:
            try:
                return pd.read_csv(csv_path, encoding=encoding, sep=sep, low_memory=False)
            except Exception:
                try:
                    return pd.read_csv(
                        csv_path, encoding=encoding, sep=sep,
                        engine="python", on_bad_lines="skip", low_memory=False,
                    )
                except Exception:
                    continue
    raise ValueError(f"Cannot read CSV: {csv_path}")


def enrich_training_df(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived features: statistical_region, building_age, log_size_m2."""
    result = df.copy()

    if "municipality" in result.columns:
        normalized = result["municipality"].apply(normalize_text)
        result["statistical_region"] = normalized.apply(lookup_region)

    if "year_built" in result.columns:
        current_year = pd.Timestamp.now().year
        result["building_age"] = current_year - pd.to_numeric(result["year_built"], errors="coerce")
        result["building_age"] = result["building_age"].clip(lower=0)
    else:
        result["building_age"] = np.nan

    if "size_m2" in result.columns:
        result["log_size_m2"] = np.log1p(
            pd.to_numeric(result["size_m2"], errors="coerce").fillna(0).clip(lower=0)
        )
    else:
        result["log_size_m2"] = np.nan

    for col in ["num_prostori", "has_klet", "has_garaza", "has_terasa", "has_shramba", "ddv_vkljucen"]:
        if col not in result.columns:
            result[col] = 0

    if "stavba_je_dokoncana" not in result.columns:
        result["stavba_je_dokoncana"] = 1
    if "uporabna_povrsina" not in result.columns:
        result["uporabna_povrsina"] = np.nan
    if "lega_v_stavbi" not in result.columns:
        result["lega_v_stavbi"] = "unknown"
    if "transaction_year" not in result.columns:
        result["transaction_year"] = pd.Timestamp.now().year
    if "novogradnja" not in result.columns:
        result["novogradnja"] = 0

    return result


def prepare_training_csv(
    source_csv_path: str, column_map: dict[str, str], output_csv_path: str,
) -> dict[str, Any]:
    df = read_csv_flexible(source_csv_path)
    renamed = df.rename(columns=column_map)

    required = [
        "size_m2", "rooms", "year_built", "floor",
        "latitude", "longitude", "municipality", "property_type", "price_eur",
    ]
    missing = [col for col in required if col not in renamed.columns]
    if missing:
        raise ValueError(f"Missing columns after mapping: {', '.join(missing)}")

    training_df = renamed[required].copy()
    training_df = enrich_training_df(training_df)

    os.makedirs(os.path.dirname(output_csv_path), exist_ok=True)
    training_df.to_csv(output_csv_path, index=False)

    return {
        "output_csv_path": output_csv_path,
        "rows": len(training_df),
        "columns": list(training_df.columns),
    }
