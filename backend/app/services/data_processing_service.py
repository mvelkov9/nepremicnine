"""Data processing service — ETN CSV parsing, feature extraction, training data preparation."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import struct as _struct
import unicodedata
import uuid
import zipfile
from typing import Any

import numpy as np
import pandas as pd

from app.services.regions_service import FALLBACK_REGIONS, lookup_region, lookup_region_by_code, normalize
from app.utils.municipality import normalize_municipality_name
from app.utils.slovenian_labels import format_municipality_label

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


def read_csv_flexible(csv_path: str) -> pd.DataFrame:
    for encoding in ["utf-8", "cp1250", "latin1"]:
        for sep in [",", ";", "\t"]:
            try:
                return pd.read_csv(csv_path, encoding=encoding, sep=sep, low_memory=False)
            except Exception:
                try:
                    return pd.read_csv(
                        csv_path,
                        encoding=encoding,
                        sep=sep,
                        engine="python",
                        on_bad_lines="skip",
                        low_memory=False,
                    )
                except Exception:
                    continue
    raise ValueError(f"Cannot read CSV: {csv_path}")


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


def _safe_extractall(archive: zipfile.ZipFile, dest: str) -> None:
    """Extract ZIP members after verifying none escape the destination directory."""
    dest = os.path.realpath(dest)
    for member in archive.namelist():
        member_path = os.path.realpath(os.path.join(dest, member))
        if not member_path.startswith(dest + os.sep) and member_path != dest:
            raise ValueError(f"ZIP member would escape target directory: {member}")
    archive.extractall(dest)


def extract_zip_csvs(zip_path: str, upload_dir: str) -> list[str]:
    """Extract a ZIP (incl. nested ZIPs) and return paths to all CSV files."""
    extract_dir = os.path.join(upload_dir, f"unzipped_{uuid.uuid4().hex}")
    os.makedirs(extract_dir, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            _safe_extractall(archive, extract_dir)

        # Expand nested ZIPs
        for root, _, files in os.walk(extract_dir):
            for fname in files:
                if fname.lower().endswith(".zip"):
                    nested_path = os.path.join(root, fname)
                    nested_dir = os.path.join(root, f"inner_{os.path.splitext(fname)[0]}")
                    os.makedirs(nested_dir, exist_ok=True)
                    try:
                        with zipfile.ZipFile(nested_path, "r") as nested:
                            _safe_extractall(nested, nested_dir)
                    except (zipfile.BadZipFile, ValueError):
                        continue

        csv_paths: list[str] = []
        for root, _, files in os.walk(extract_dir):
            for fname in files:
                if fname.lower().endswith(".csv"):
                    src = os.path.join(root, fname)
                    safe_name = fname.replace("/", "_").replace("\\", "_")
                    dst = os.path.join(upload_dir, f"{uuid.uuid4().hex}_{safe_name}")
                    shutil.move(src, dst)
                    csv_paths.append(dst)
        return csv_paths
    finally:
        shutil.rmtree(extract_dir, ignore_errors=True)


def extract_zip_all(zip_path: str, upload_dir: str) -> str:
    """Extract ZIP (incl. nested ZIPs) and return the extraction directory."""
    extract_dir = os.path.join(upload_dir, f"unzipped_{uuid.uuid4().hex}")
    os.makedirs(extract_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as archive:
        _safe_extractall(archive, extract_dir)

    for root, _, files in os.walk(extract_dir):
        for fname in files:
            if fname.lower().endswith(".zip"):
                nested_path = os.path.join(root, fname)
                nested_dir = os.path.join(root, f"inner_{os.path.splitext(fname)[0]}")
                os.makedirs(nested_dir, exist_ok=True)
                try:
                    with zipfile.ZipFile(nested_path, "r") as nested:
                        _safe_extractall(nested, nested_dir)
                except (zipfile.BadZipFile, ValueError):
                    continue
    return extract_dir


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

    training_df["ime_ko"] = (
        merged["IME_KO"].apply(clean_display_text) if "IME_KO" in merged.columns else "unknown"
    )
    training_df["naselje"] = (
        merged["NASELJE"].apply(clean_display_text) if "NASELJE" in merged.columns else "unknown"
    )
    training_df["vrsta_dela_stavbe"] = (
        merged["VRSTA_DELA_STAVBE"].apply(clean_display_text) if "VRSTA_DELA_STAVBE" in merged.columns else "unknown"
    )
    training_df["evidentiranost_dela_stavbe"] = (
        pd.to_numeric(merged.get("EVIDENTIRANOST_DELA_STAVBE", np.nan), errors="coerce")
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
                lambda values: clean_display_text(values.dropna().astype(str).mode().iloc[0])
                if len(values.dropna())
                else "unknown"
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
                weighted_sum = (parcel_share_df.loc[valid, "parcel_share"] * parcel_share_df.loc[valid, "parcel_area"])
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
) -> dict[str, Any]:
    """Prepare training CSV from ETN KPP posli + delistavb pair."""
    posli_df = read_csv_flexible(posli_csv_path)
    deli_df = read_csv_flexible(delistavb_csv_path)
    training_df, meta = build_training_df_from_etn_kpp(posli_df, deli_df)

    os.makedirs(os.path.dirname(output_csv_path), exist_ok=True)
    training_df.to_csv(output_csv_path, index=False)
    _write_training_metadata(
        output_csv_path,
        {
            "source": "etn_kpp",
            "rows": len(training_df),
            "columns": list(training_df.columns),
            "reports": [{"label": "single", "status": "ok", "rows": len(training_df), **meta}],
            "filter_summary": {
                "building": _aggregate_stage_sequences([meta.get("filter_stats", {}).get("stages", [])]),
                "land": [],
            },
        },
    )

    return {
        "output_csv_path": output_csv_path,
        "rows": len(training_df),
        "columns": list(training_df.columns),
        "source": "etn_kpp",
        **meta,
    }


def prepare_training_csv_from_etn_kpp_bulk(
    pairs: list[dict[str, Any]],
    output_csv_path: str,
) -> dict[str, Any]:
    """Prepare training CSV from multiple ETN KPP pairs (multi-year)."""
    if not pairs:
        raise ValueError("No ETN pairs provided.")

    training_frames: list[pd.DataFrame] = []
    reports: list[dict[str, Any]] = []

    for pair in pairs:
        posli_csv_path = pair.get("posli_csv_path")
        delistavb_csv_path = pair.get("delistavb_csv_path")
        zemljisca_csv_path = pair.get("zemljisca_csv_path")
        label = str(pair.get("label") or pair.get("year") or "unknown")

        if not posli_csv_path or not delistavb_csv_path:
            reports.append({"label": label, "status": "skipped", "reason": "missing paths"})
            continue

        posli_df = read_csv_flexible(posli_csv_path)
        deli_df = read_csv_flexible(delistavb_csv_path)
        zemljisca_df = None
        if zemljisca_csv_path:
            with contextlib.suppress(Exception):
                zemljisca_df = read_csv_flexible(zemljisca_csv_path)

        try:
            frame, meta = build_training_df_from_etn_kpp(posli_df, deli_df, zemljisca_df)
            frame["source_label"] = label
            frame["transaction_year"] = pd.to_numeric(label, errors="coerce")
            training_frames.append(frame)
            report = {
                "label": label,
                "status": "ok",
                "rows": len(frame),
                **meta,
                "building_filter_stats": meta.get("filter_stats", {}).get("stages", []),
            }

            if zemljisca_df is not None:
                land_only_ids = set(deli_df["ID_POSLA"].astype(str)) if "ID_POSLA" in deli_df.columns else set()
                with contextlib.suppress(Exception):
                    land_frame, land_meta = build_training_df_from_etn_kpp_land(
                        posli_df,
                        zemljisca_df,
                        exclude_posli_ids=land_only_ids,
                    )
                    land_frame["source_label"] = label
                    land_frame["transaction_year"] = pd.to_numeric(label, errors="coerce")
                    training_frames.append(land_frame)
                    report["parcel_rows"] = len(land_frame)
                    report["rows"] += len(land_frame)
                    report["land_filter_stats"] = land_meta.get("filter_stats", {}).get("stages", [])

            reports.append(report)
        except Exception as exc:
            reports.append({"label": label, "status": "error", "reason": str(exc)})

    if not training_frames:
        raise ValueError("No valid ETN pairs produced training data.")

    combined = pd.concat(training_frames, ignore_index=True)
    rows_before_dedup = len(combined)
    dedupe_columns = [col for col in ["source_label", "source_row_key"] if col in combined.columns]
    if dedupe_columns:
        combined = combined.drop_duplicates(subset=dedupe_columns)
    deduplicated_rows = rows_before_dedup - len(combined)
    per_year = {
        str(label): int(rows)
        for label, rows in combined.groupby("source_label", dropna=False).size().sort_index().items()
    }

    os.makedirs(os.path.dirname(output_csv_path), exist_ok=True)
    combined.to_csv(output_csv_path, index=False)

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
            "rows": len(combined),
            "columns": list(combined.columns),
            "pairs_received": len(pairs),
            "pairs_used": len(training_frames),
            "deduplicated_rows": deduplicated_rows,
            "per_year": per_year,
            "reports": reports,
            "filter_summary": filter_summary,
        },
    )

    return {
        "output_csv_path": output_csv_path,
        "rows": len(combined),
        "columns": list(combined.columns),
        "source": "etn_kpp_bulk",
        "pairs_received": len(pairs),
        "pairs_used": len(training_frames),
        "deduplicated_rows": deduplicated_rows,
        "per_year": per_year,
        "filter_summary": filter_summary,
        "reports": reports,
    }
