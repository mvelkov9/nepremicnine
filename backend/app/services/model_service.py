"""Model training & prediction service — HistGradientBoosting per-type architecture."""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable
from math import isnan
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import TargetEncoder

from app.services.data_processing_service import (
    EXCLUDED_PROPERTY_TYPES,
    enrich_training_df,
    load_training_metadata,
    read_csv_flexible,
)
from app.utils.municipality import normalize_municipality_name

logger = logging.getLogger(__name__)

NUMERIC_FEATURES = [
    "size_m2",
    "year_built",
    "rooms",
    "floor",
    "latitude",
    "longitude",
    "building_age",
    "novogradnja",
    "num_prostori",
    "has_klet",
    "has_garaza",
    "has_terasa",
    "has_shramba",
    "has_parking",
    "uporabna_povrsina",
    "parcela_m2",
    "prodani_delez_parcele",
    "prodani_delez_dela_stavbe",
    "gradbena_faza",
    "stavba_je_dokoncana",
    "ddv_vkljucen",
    "log_size_m2",
    "transaction_year",
    "transaction_quarter",
    "price_per_m2_region",
    "price_per_m2_type",
    "price_per_m2_municipality",
    # Spatial distance features (ETRS89/TM metric coordinates → Euclidean distance in meters)
    "dist_ljubljana",
    "dist_maribor",
    "dist_coast",
    # Type-specific comparable-sales features (computed per-type from training data)
    "comp_type_muni_ppm2",
    "comp_type_ko_ppm2",
    # ── Enrichment features (EV/EMV/GJI/KN/RN registers) ──
    "emv_zone_level",
    "emv_zone_id",
    "ev_ima_dvigalo",
    "ev_ima_vodovod",
    "ev_ima_kanalizacijo",
    "ev_ima_elektriko",
    "ev_ima_plin",
    "ev_leto_izg_stavbe",
    "ev_st_etaz",
    "ev_st_stanovanj",
    "ev_st_poslovnih_prostorov",
    "ev_del_st_nadstropja",
    "ev_del_povrsina",
    "ev_del_upor_pov",
    "ev_pov_stavbe",
    "ev_visina_etaze",
    "ev_id_lega",
    "ev_id_dr_dst",
    "ev_id_tip_stavbe",
    "ev_leto_obn_strehe",
    "ev_leto_obn_fasade",
    "ev_leto_obn_oken",
    "ev_leto_obn_inst",
    "ev_parcela_povrsina",
    "ev_boniteta",
    "ev_odprtost",
    "gji_kanalizacija_distance_m",
    "gji_kanalizacija_nearby_100m",
    "gji_vodovod_distance_m",
    "gji_vodovod_nearby_100m",
    "kn_ggo_openness",
    "rn_address_match",
    "stopnja_ddv",
    "vrsta_dela_stavbe",
]

CATEGORICAL_FEATURES = [
    "municipality_normalized",
    "property_type",
    "statistical_region",
    "lega_v_stavbi",
    "ime_ko",
    "naselje",
    "vrsta_zemljisca",
    "vrsta_kupoprodajnega_posla",
    # Enrichment categoricals — strong location proxies
    "emv_zone_name",
    "emv_zone_model",
    "kn_ggo_section",
]

PERTYPE_NUMERIC = [f for f in NUMERIC_FEATURES if f != "price_per_m2_type"]
PERTYPE_CATEGORICAL = [f for f in CATEGORICAL_FEATURES if f != "property_type"]

MIN_SAMPLES_PER_TYPE = 200

# Core features to always keep even with low fill rates (global model defaults)
ALWAYS_INCLUDE_NUMERIC = {
    "size_m2",
    "year_built",
    "novogradnja",
    "has_klet",
    "has_garaza",
    "has_terasa",
    "has_shramba",
    "has_parking",
    "prodani_delez_parcele",
    "prodani_delez_dela_stavbe",
    "gradbena_faza",
    "stavba_je_dokoncana",
    "log_size_m2",
    "transaction_year",
    "price_per_m2_region",
    "dist_ljubljana",
    "dist_maribor",
    "dist_coast",
    "comp_type_muni_ppm2",
    "comp_type_ko_ppm2",
    "emv_zone_level",
}

ALWAYS_INCLUDE_CATEGORICAL = {
    "municipality_normalized",
    "statistical_region",
    "lega_v_stavbi",
    "emv_zone_name",
}

FEATURE_LABELS_SL: dict[str, str] = {
    "size_m2": "Velikost (m²)",
    "rooms": "Število sob",
    "year_built": "Leto izgradnje",
    "floor": "Nadstropje",
    "latitude": "GPS širina",
    "longitude": "GPS dolžina",
    "municipality_normalized": "Občina",
    "property_type": "Vrsta nepremičnine",
    "statistical_region": "Statistična regija",
    "building_age": "Starost stavbe",
    "log_size_m2": "Log velikost",
    "novogradnja": "Novogradnja",
    "num_prostori": "Št. prostorov",
    "has_klet": "Klet",
    "has_garaza": "Garaža",
    "has_terasa": "Terasa",
    "has_shramba": "Shramba",
    "has_parking": "Parkirno mesto",
    "uporabna_povrsina": "Uporabna površina",
    "parcela_m2": "Površina parcele",
    "prodani_delez_parcele": "Prodani delež parcele",
    "prodani_delez_dela_stavbe": "Prodani delež dela stavbe",
    "gradbena_faza": "Gradbena faza",
    "stopnja_ddv": "Stopnja DDV",
    "evidentiranost_dela_stavbe": "Evidentiranost dela stavbe",
    "atrij": "Atrij",
    "stavba_je_dokoncana": "Stavba dokončana",
    "ddv_vkljucen": "DDV vključen",
    "lega_v_stavbi": "Lega v stavbi",
    "transaction_year": "Leto transakcije",
    "transaction_quarter": "Četrtletje transakcije",
    "price_per_m2_region": "€/m² regija",
    "price_per_m2_type": "€/m² tip",
    "price_per_m2_municipality": "€/m² občina",
    "ime_ko": "Katastrska občina",
    "naselje": "Naselje",
    "vrsta_dela_stavbe": "Vrsta dela stavbe",
    "vrsta_zemljisca": "Vrsta zemljišča",
    "vrsta_kupoprodajnega_posla": "Vrsta kupoprodajnega posla",
    "dist_ljubljana": "Razdalja do Ljubljane",
    "dist_maribor": "Razdalja do Maribora",
    "dist_coast": "Razdalja do obale",
    "comp_type_muni_ppm2": "€/m² tip+občina",
    "comp_type_ko_ppm2": "€/m² tip+KO",
    "comp_type_zone_ppm2": "€/m² tip+EMV cona",
    "comp_type_naselje_ppm2": "€/m² tip+naselje",
    # Enrichment feature labels
    "emv_zone_level": "EMV raven cone",
    "emv_zone_id": "EMV cona ID",
    "ev_ima_dvigalo": "Dvigalo",
    "ev_ima_vodovod": "Vodovod",
    "ev_ima_kanalizacijo": "Kanalizacija",
    "ev_ima_elektriko": "Elektrika",
    "ev_ima_plin": "Plin",
    "ev_leto_izg_stavbe": "Leto izgradnje (EV)",
    "ev_st_etaz": "Št. etaž",
    "ev_st_stanovanj": "Št. stanovanj",
    "ev_st_poslovnih_prostorov": "Št. poslovnih prostorov",
    "ev_del_st_nadstropja": "Nadstropje (EV)",
    "ev_del_povrsina": "Površina dela (EV)",
    "ev_del_upor_pov": "Uporabna površina (EV)",
    "ev_pov_stavbe": "Površina stavbe",
    "ev_visina_etaze": "Višina etaže",
    "ev_id_lega": "Lega (EV)",
    "ev_id_dr_dst": "Vrsta dela stavbe (EV)",
    "ev_id_tip_stavbe": "Tip stavbe (EV)",
    "ev_leto_obn_strehe": "Obnova strehe",
    "ev_leto_obn_fasade": "Obnova fasade",
    "ev_leto_obn_oken": "Obnova oken",
    "ev_leto_obn_inst": "Obnova instalacij",
    "ev_parcela_povrsina": "Površina parcele (EV)",
    "ev_boniteta": "Boniteta",
    "ev_odprtost": "Odprtost",
    "gji_kanalizacija_distance_m": "Razdalja do kanalizacije",
    "gji_kanalizacija_nearby_100m": "Kanalizacija v 100m",
    "gji_vodovod_distance_m": "Razdalja do vodovoda",
    "gji_vodovod_nearby_100m": "Vodovod v 100m",
    "kn_ggo_openness": "GGO odprtost",
    "rn_address_match": "Ujemanje naslova",
    "stopnja_ddv": "Stopnja DDV",
    "vrsta_dela_stavbe": "Vrsta dela stavbe",
    "emv_zone_name": "EMV cona ime",
    "emv_zone_model": "EMV model vrednotenja",
    "kn_ggo_section": "GGO odsek",
}

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "models")

_MIN_FILL_RATE = 0.10
_MIN_SIGNAL_SCORE = 0.01
_MAX_EXTRA_NUMERIC = 8
_MAX_EXTRA_CATEGORICAL = 8
_model_cache: dict | None = None
_model_cache_mtime: float = 0.0

PARCELA_ALWAYS_INCLUDE_NUMERIC = {
    "size_m2",
    "parcela_m2",
    "prodani_delez_parcele",
    "latitude",
    "longitude",
    "log_size_m2",
    "transaction_year",
    "price_per_m2_region",
    "price_per_m2_municipality",
    "ddv_vkljucen",
    "dist_ljubljana",
    "dist_maribor",
    "dist_coast",
    "comp_type_muni_ppm2",
    "comp_type_ko_ppm2",
    # Enrichment: strongest correlators for parcela (|r|=0.30–0.76)
    "emv_zone_id",
    "emv_zone_level",
    "gji_kanalizacija_nearby_100m",
    "gji_vodovod_nearby_100m",
    "gji_kanalizacija_distance_m",
    "gji_vodovod_distance_m",
    "ev_parcela_povrsina",
    "ev_boniteta",
    "kn_ggo_openness",
}

PARCELA_ALWAYS_INCLUDE_CATEGORICAL = {
    "municipality_normalized",
    "statistical_region",
    "ime_ko",
    "naselje",
    "vrsta_zemljisca",
    "emv_zone_name",
}

# ── Type-specific feature configurations ─────────────────────────────
# Each type gets its own "always include" set — signal scoring adds more on top.
# _SPATIAL_ALWAYS is added to every type's always_numeric automatically.
_SPATIAL_ALWAYS = {"dist_ljubljana", "dist_maribor", "dist_coast", "comp_type_muni_ppm2", "comp_type_ko_ppm2"}

TYPE_FEATURE_CONFIGS: dict[str, dict[str, set[str]]] = {
    "stanovanje": {
        "always_numeric": {
            "size_m2",
            "year_built",
            "rooms",
            "floor",
            "building_age",
            "novogradnja",
            "log_size_m2",
            "transaction_year",
            "price_per_m2_region",
            "price_per_m2_municipality",
            "prodani_delez_dela_stavbe",
            "stavba_je_dokoncana",
            "uporabna_povrsina",
            "num_prostori",
            # Enrichment (|r| > 0.15, fill > 25%)
            "emv_zone_level",       # r=0.65
            "emv_zone_id",          # zone granularity
            "ev_st_etaz",           # r=0.26
            "ev_ima_kanalizacijo",  # r=0.26
            "ev_id_dr_dst",         # r=-0.26
            "gji_kanalizacija_nearby_100m",  # r=0.24
            "ev_leto_izg_stavbe",   # r=0.23
            "ev_st_stanovanj",      # r=0.22
            "ev_ima_dvigalo",       # r=0.21
            "gji_kanalizacija_distance_m",  # r=-0.20
            "ev_del_st_nadstropja", # r=0.19
            "vrsta_dela_stavbe",    # r=-0.18
            "ev_pov_stavbe",        # r=0.17
        }
        | _SPATIAL_ALWAYS,
        "always_categorical": {
            "municipality_normalized",
            "statistical_region",
            "lega_v_stavbi",
            "ime_ko",
            "naselje",
            "emv_zone_name",
        },
    },
    "hisa": {
        "always_numeric": {
            "size_m2",
            "year_built",
            "rooms",
            "building_age",
            "novogradnja",
            "log_size_m2",
            "transaction_year",
            "price_per_m2_region",
            "price_per_m2_municipality",
            "parcela_m2",
            "stavba_je_dokoncana",
            "uporabna_povrsina",
            "latitude",
            "longitude",
            "has_parking",
            # Enrichment (|r| > 0.15, fill > 15%)
            "emv_zone_level",       # r=0.59
            "ev_leto_izg_stavbe",   # r=0.28
            "ev_ima_kanalizacijo",  # r=0.28
            "ev_leto_obn_strehe",   # r=0.26
            "ev_leto_obn_fasade",   # r=0.25
            "gji_kanalizacija_nearby_100m",  # r=0.24
            "ev_leto_obn_oken",     # r=0.23
            "ev_ima_plin",          # r=0.22
            "ev_id_tip_stavbe",     # r=0.22
            "ev_leto_obn_inst",     # r=0.22
            "gji_kanalizacija_distance_m",  # r=-0.21
            "ev_ima_vodovod",       # r=0.19
            "emv_zone_id",          # r=-0.19
            "rn_address_match",     # r=0.16
        }
        | _SPATIAL_ALWAYS,
        "always_categorical": {
            "municipality_normalized",
            "statistical_region",
            "ime_ko",
            "naselje",
            "emv_zone_name",
        },
    },
    "parcela": {
        "always_numeric": PARCELA_ALWAYS_INCLUDE_NUMERIC,
        "always_categorical": PARCELA_ALWAYS_INCLUDE_CATEGORICAL,
    },
    "kmetijsko": {
        "always_numeric": {
            "size_m2",
            "parcela_m2",
            "prodani_delez_parcele",
            "latitude",
            "longitude",
            "log_size_m2",
            "transaction_year",
            "price_per_m2_region",
            "price_per_m2_municipality",
            "ddv_vkljucen",
            # Enrichment (|r| > 0.12, fill > 10%)
            "emv_zone_level",       # r=0.38
            "emv_zone_id",
            "gji_kanalizacija_distance_m",  # r=-0.17
            "gji_vodovod_distance_m",
            "ev_leto_izg_stavbe",   # r=0.15
            "gji_kanalizacija_nearby_100m",  # r=0.13
            "ev_del_upor_pov",      # r=-0.12
            "ev_boniteta",
            "kn_ggo_openness",
        }
        | _SPATIAL_ALWAYS,
        "always_categorical": {
            "municipality_normalized",
            "statistical_region",
            "vrsta_zemljisca",
            "ime_ko",
            "emv_zone_name",
            "kn_ggo_section",
        },
    },
    "garaza": {
        "always_numeric": {
            "size_m2",
            "year_built",
            "building_age",
            "novogradnja",
            "log_size_m2",
            "transaction_year",
            "price_per_m2_region",
            "price_per_m2_municipality",
            "stavba_je_dokoncana",
            "ddv_vkljucen",
            "prodani_delez_dela_stavbe",
            "latitude",
            "longitude",
            # Enrichment (|r| > 0.20, fill > 30%)
            "emv_zone_level",       # r=0.45
            "emv_zone_id",
            "ev_leto_izg_stavbe",   # r=0.40
            "stopnja_ddv",          # r=-0.40
            "ev_ima_dvigalo",       # r=0.37
            "ev_ima_vodovod",       # r=0.36
            "ev_ima_kanalizacijo",  # r=0.35
            "ev_id_lega",           # r=-0.33
            "ev_ima_elektriko",     # r=0.33
            "gji_kanalizacija_nearby_100m",  # r=0.23
            "ev_del_st_nadstropja", # r=-0.22
            "ev_st_etaz",           # r=0.22
            "ev_ima_plin",          # r=0.23
        }
        | _SPATIAL_ALWAYS,
        "always_categorical": {
            "municipality_normalized",
            "statistical_region",
            "lega_v_stavbi",
            "ime_ko",
            "emv_zone_name",
        },
    },
    "poslovni_prostor": {
        "always_numeric": {
            "size_m2",
            "year_built",
            "floor",
            "building_age",
            "novogradnja",
            "log_size_m2",
            "transaction_year",
            "price_per_m2_region",
            "price_per_m2_municipality",
            "uporabna_povrsina",
            "prodani_delez_dela_stavbe",
            "stavba_je_dokoncana",
            "ddv_vkljucen",
            # Enrichment (|r| > 0.15, fill > 15%)
            "emv_zone_level",       # r=0.59
            "emv_zone_id",
            "ev_ima_dvigalo",       # r=0.29
            "ev_ima_kanalizacijo",  # r=0.29
            "ev_st_etaz",           # r=0.24
            "gji_kanalizacija_nearby_100m",  # r=0.18
            "ev_st_poslovnih_prostorov",  # r=0.17
            "ev_leto_izg_stavbe",   # r=0.15
        }
        | _SPATIAL_ALWAYS,
        "always_categorical": {
            "municipality_normalized",
            "statistical_region",
            "lega_v_stavbi",
            "ime_ko",
            "naselje",
            "emv_zone_name",
        },
    },
    "industrijski": {
        "always_numeric": {
            "size_m2",
            "year_built",
            "building_age",
            "novogradnja",
            "log_size_m2",
            "transaction_year",
            "price_per_m2_region",
            "price_per_m2_municipality",
            "uporabna_povrsina",
            "parcela_m2",
            "prodani_delez_dela_stavbe",
            "stavba_je_dokoncana",
            "latitude",
            "longitude",
            # Enrichment (|r| > 0.18, fill > 30%)
            "ev_ima_dvigalo",       # r=0.55
            "emv_zone_level",       # r=0.34
            "emv_zone_id",
            "ev_id_dr_dst",         # r=-0.33
            "ev_ima_vodovod",       # r=0.29
            "ev_ima_kanalizacijo",  # r=0.28
            "ev_ima_elektriko",     # r=0.25
            "ev_st_etaz",           # r=0.24
            "ev_del_upor_pov",      # r=-0.23
            "rn_address_match",     # r=0.19
        }
        | _SPATIAL_ALWAYS,
        "always_categorical": {
            "municipality_normalized",
            "statistical_region",
            "ime_ko",
            "emv_zone_name",
        },
    },
    "turisticni": {
        "always_numeric": {
            "size_m2",
            "year_built",
            "rooms",
            "building_age",
            "novogradnja",
            "log_size_m2",
            "transaction_year",
            "price_per_m2_region",
            "price_per_m2_municipality",
            "uporabna_povrsina",
            "prodani_delez_dela_stavbe",
            "stavba_je_dokoncana",
            "latitude",
            "longitude",
            # Enrichment (|r| > 0.15, fill > 30%)
            "emv_zone_level",       # r=0.52
            "emv_zone_id",
            "ev_ima_dvigalo",       # r=0.45
            "gji_kanalizacija_nearby_100m",  # r=0.32
            "ev_ima_kanalizacijo",  # r=0.23
            "ev_del_povrsina",      # r=-0.20
            "ev_st_etaz",           # r=0.20
            "ev_del_upor_pov",      # r=-0.19
            "gji_kanalizacija_distance_m",  # r=-0.18
        }
        | _SPATIAL_ALWAYS,
        "always_categorical": {
            "municipality_normalized",
            "statistical_region",
            "ime_ko",
            "naselje",
            "emv_zone_name",
        },
    },
    "gostinstvo": {
        "always_numeric": {
            "size_m2",
            "year_built",
            "building_age",
            "log_size_m2",
            "transaction_year",
            "price_per_m2_region",
            "price_per_m2_municipality",
            "uporabna_povrsina",
            "stavba_je_dokoncana",
            "latitude",
            "longitude",
            # Enrichment (|r| > 0.14, fill > 30%)
            "emv_zone_level",       # r=0.52
            "ev_ima_kanalizacijo",  # r=0.20
            "emv_zone_id",          # r=-0.20
            "gji_kanalizacija_nearby_100m",  # r=0.18
            "ev_st_stanovanj",      # r=0.16
            "ev_ima_vodovod",       # r=0.16
            "ev_st_poslovnih_prostorov",  # r=0.16
            "ev_st_etaz",           # r=0.15
        }
        | _SPATIAL_ALWAYS,
        "always_categorical": {
            "municipality_normalized",
            "statistical_region",
            "ime_ko",
            "emv_zone_name",
        },
    },
}


# ── Enrichment source definitions (for variant benchmarking) ─────────
_ENRICHMENT_PREFIXES: dict[str, tuple[str, ...]] = {
    "rn": ("rn_",),
    "ev": ("ev_",),
    "kn": ("kn_",),
    "gji": ("gji_",),
    "emv": ("emv_",),
}

_VARIANT_CONFIGS: dict[str, dict[str, bool]] = {
    "etn_only": {"rn": False, "ev": False, "kn": False, "gji": False, "emv": False},
    "deterministic": {"rn": True, "ev": True, "kn": True, "gji": False, "emv": False},
    "full_global": {"rn": True, "ev": True, "kn": True, "gji": True, "emv": True},
}


def _normalize_categorical_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Normalize mixed-type categorical columns to uniform strings."""
    df = df.copy()
    for col in columns:
        if col not in df.columns:
            continue
        df[col] = df[col].apply(
            lambda v: "unknown" if v is None or (isinstance(v, float) and np.isnan(v)) else str(v)
        )
        df[col] = df[col].apply(lambda v: "unknown" if not v or v.isspace() else v)
    return df


def _filter_features_by_source(
    features: list[str], enabled_sources: dict[str, bool]
) -> list[str]:
    """Filter feature list based on which enrichment sources are enabled."""
    result = []
    for f in features:
        excluded = False
        for source, prefixes in _ENRICHMENT_PREFIXES.items():
            if any(f.startswith(p) for p in prefixes):
                if not enabled_sources.get(source, True):
                    excluded = True
                break
        if not excluded:
            result.append(f)
    return result


def _filter_features(
    df: pd.DataFrame,
    candidate_numeric: list[str],
    candidate_categorical: list[str],
) -> tuple[list[str], list[str]]:
    """Filter features by fill rate, keeping ALWAYS_INCLUDE even when sparse."""
    numeric = [
        c
        for c in candidate_numeric
        if c in df.columns
        and (df[c].notna().mean() >= _MIN_FILL_RATE or (c in ALWAYS_INCLUDE_NUMERIC and df[c].notna().any()))
        and pd.to_numeric(df[c], errors="coerce").dropna().nunique() > 1
    ]
    categorical = [
        c
        for c in candidate_categorical
        if c in df.columns
        and (df[c].notna().mean() >= _MIN_FILL_RATE or (c in ALWAYS_INCLUDE_CATEGORICAL and df[c].notna().any()))
        and df[c].fillna("unknown").astype(str).nunique() > 1
    ]
    return numeric, categorical


def _adaptive_hyperparams(n_samples: int) -> dict:
    if n_samples > 50_000:
        return {
            "max_iter": 6000,
            "learning_rate": 0.008,
            "max_depth": 10,
            "min_samples_leaf": 25,
            "l2_regularization": 0.02,
        }
    if n_samples > 20_000:
        return {
            "max_iter": 5000,
            "learning_rate": 0.01,
            "max_depth": 9,
            "min_samples_leaf": 20,
            "l2_regularization": 0.03,
        }
    if n_samples > 5000:
        return {
            "max_iter": 4000,
            "learning_rate": 0.015,
            "max_depth": 8,
            "min_samples_leaf": 15,
            "l2_regularization": 0.04,
        }
    if n_samples > 1000:
        return {
            "max_iter": 3000,
            "learning_rate": 0.02,
            "max_depth": 7,
            "min_samples_leaf": 12,
            "l2_regularization": 0.06,
        }
    if n_samples > 500:
        return {
            "max_iter": 2000,
            "learning_rate": 0.03,
            "max_depth": 6,
            "min_samples_leaf": 10,
            "l2_regularization": 0.1,
        }
    return {
        "max_iter": 1500,
        "learning_rate": 0.04,
        "max_depth": 5,
        "min_samples_leaf": 8,
        "l2_regularization": 0.15,
    }


def _adaptive_max_extras(n_samples: int) -> tuple[int, int]:
    """Return (max_extra_numeric, max_extra_categorical) based on dataset size."""
    if n_samples > 10_000:
        return 20, 12
    if n_samples > 3000:
        return 16, 10
    if n_samples > 1000:
        return 12, 8
    if n_samples > 500:
        return 8, 6
    return 6, 4


def _safe_abs(value: float | None) -> float:
    if value is None:
        return 0.0
    if isnan(value):
        return 0.0
    return abs(float(value))


def _score_numeric_feature(series: pd.Series, target: pd.Series) -> float:
    numeric = pd.to_numeric(series, errors="coerce")
    valid = numeric.notna() & target.notna()
    if valid.sum() < 50 or numeric[valid].nunique() <= 1:
        return 0.0
    return _safe_abs(numeric[valid].corr(target[valid], method="spearman"))


def _score_categorical_feature(series: pd.Series, target: pd.Series) -> float:
    categorical = series.fillna("unknown").astype(str)
    valid = target.notna()
    categorical = categorical[valid]
    target = target[valid]
    if len(categorical) < 50 or categorical.nunique() <= 1:
        return 0.0
    grouped = pd.DataFrame({"value": categorical, "target": target})
    means = grouped.groupby("value")["target"].mean()
    encoded = grouped["value"].map(means)
    return _safe_abs(encoded.corr(grouped["target"]))


def _select_type_specific_features(
    df: pd.DataFrame,
    target: np.ndarray,
    candidate_numeric: list[str],
    candidate_categorical: list[str],
    *,
    always_numeric: set[str] | None = None,
    always_categorical: set[str] | None = None,
    max_extra_numeric: int = _MAX_EXTRA_NUMERIC,
    max_extra_categorical: int = _MAX_EXTRA_CATEGORICAL,
) -> tuple[list[str], list[str], dict[str, float]]:
    filtered_numeric, filtered_categorical = _filter_features(df, candidate_numeric, candidate_categorical)
    # Score features against log(price/m²) — the actual prediction target
    size_vals = pd.to_numeric(df.get("size_m2"), errors="coerce").clip(lower=1).values
    target_series = pd.Series(np.log(np.maximum(target, 1) / size_vals), index=df.index)
    always_numeric = ALWAYS_INCLUDE_NUMERIC if always_numeric is None else always_numeric
    always_categorical = ALWAYS_INCLUDE_CATEGORICAL if always_categorical is None else always_categorical

    scores: dict[str, float] = {}
    for col in filtered_numeric:
        scores[col] = _score_numeric_feature(df[col], target_series)
    for col in filtered_categorical:
        scores[col] = _score_categorical_feature(df[col], target_series)

    always_numeric_selected = [col for col in filtered_numeric if col in always_numeric]
    always_categorical_selected = [col for col in filtered_categorical if col in always_categorical]

    ranked_numeric = sorted(
        [col for col in filtered_numeric if col not in always_numeric_selected],
        key=lambda col: (scores.get(col, 0.0), df[col].notna().mean()),
        reverse=True,
    )
    ranked_categorical = sorted(
        [col for col in filtered_categorical if col not in always_categorical_selected],
        key=lambda col: (scores.get(col, 0.0), df[col].notna().mean()),
        reverse=True,
    )

    selected_numeric = (
        always_numeric_selected
        + [col for col in ranked_numeric if scores.get(col, 0.0) >= _MIN_SIGNAL_SCORE][:max_extra_numeric]
    )
    selected_categorical = (
        always_categorical_selected
        + [col for col in ranked_categorical if scores.get(col, 0.0) >= _MIN_SIGNAL_SCORE][:max_extra_categorical]
    )

    if "size_m2" in filtered_numeric and "size_m2" not in selected_numeric:
        selected_numeric = ["size_m2"] + selected_numeric

    return selected_numeric, selected_categorical, scores


def _build_pipeline(
    numeric_feats: list[str],
    categorical_feats: list[str],
    n_samples: int,
    y_train: np.ndarray | None = None,
    *,
    use_early_stopping: bool = False,
) -> Pipeline:
    numeric_transformer = SimpleImputer(strategy="median")
    categorical_transformer = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="constant", fill_value="unknown")),
            ("target_enc", TargetEncoder(smooth="auto")),
        ]
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, numeric_feats),
            ("cat", categorical_transformer, categorical_feats),
        ],
        remainder="drop",
    )

    hp = _adaptive_hyperparams(n_samples)

    # Early stopping requires warm_start=False (sklearn limitation).
    # Per-type models use early stopping; global model uses warm_start for progress.
    if use_early_stopping:
        model = HistGradientBoostingRegressor(
            loss="squared_error",
            max_iter=hp["max_iter"],
            learning_rate=hp["learning_rate"],
            max_depth=hp["max_depth"],
            min_samples_leaf=hp.get("min_samples_leaf", 20),
            max_bins=255,
            l2_regularization=hp.get("l2_regularization", 0.1),
            early_stopping=True,
            validation_fraction=0.12,
            n_iter_no_change=80,
            random_state=42,
            warm_start=False,
            verbose=0,
        )
    else:
        model = HistGradientBoostingRegressor(
            loss="squared_error",
            max_iter=hp["max_iter"],
            learning_rate=hp["learning_rate"],
            max_depth=hp["max_depth"],
            min_samples_leaf=hp.get("min_samples_leaf", 20),
            max_bins=255,
            l2_regularization=hp.get("l2_regularization", 0.1),
            random_state=42,
            warm_start=True,
            verbose=0,
        )

    return Pipeline([("preprocessor", preprocessor), ("regressor", model)])


def _compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    mask = y_true > 0
    y_t = y_true[mask]
    y_p = y_pred[mask]
    if len(y_t) == 0:
        return {}
    mae = float(mean_absolute_error(y_t, y_p))
    rmse = float(np.sqrt(mean_squared_error(y_t, y_p)))
    r2 = float(r2_score(y_t, y_p))
    mape = float(np.mean(np.abs((y_t - y_p) / y_t)) * 100)
    median_ae = float(np.median(np.abs(y_t - y_p)))
    return {"mae": mae, "rmse": rmse, "r2": r2, "mape": mape, "median_ae": median_ae}


def _build_segment_diagnostics(
    X_test: pd.DataFrame,
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> dict[str, list[dict[str, Any]]]:
    frame = X_test.copy()
    frame["y_true"] = y_true
    frame["y_pred"] = y_pred
    frame["abs_err"] = np.abs(frame["y_true"] - frame["y_pred"])
    frame["ape"] = np.where(frame["y_true"] > 0, frame["abs_err"] / frame["y_true"] * 100.0, np.nan)

    specs: list[tuple[str, str, int, pd.Series | None]] = [
        ("property_type", "property_type", 80, None),
        ("vrsta_kupoprodajnega_posla", "sale_type", 80, None),
        ("transaction_year", "transaction_year", 80, None),
        (
            "vrsta_zemljisca",
            "parcel_land_type",
            80,
            frame.get("property_type", pd.Series(index=frame.index, dtype="object")) == "parcela",
        ),
    ]

    diagnostics: dict[str, list[dict[str, Any]]] = {}
    for column, key, min_count, mask in specs:
        if column not in frame.columns:
            continue
        scoped = frame.loc[mask] if mask is not None else frame
        if scoped.empty:
            continue

        rows: list[dict[str, Any]] = []
        for segment, group in scoped.groupby(column, dropna=False):
            if len(group) < min_count:
                continue
            metrics = _compute_metrics(group["y_true"].to_numpy(), group["y_pred"].to_numpy())
            if not metrics:
                continue
            rows.append(
                {
                    "segment": "unknown" if pd.isna(segment) else str(segment),
                    "n": int(len(group)),
                    "r2": round(float(metrics.get("r2", 0.0)), 6),
                    "mae": round(float(metrics.get("mae", 0.0)), 2),
                    "rmse": round(float(metrics.get("rmse", 0.0)), 2),
                    "mape": round(float(metrics.get("mape", 0.0)), 2) if metrics.get("mape") is not None else None,
                    "median_ae": round(float(metrics.get("median_ae", 0.0)), 2),
                }
            )

        if rows:
            diagnostics[key] = sorted(rows, key=lambda item: (item["r2"], -item["n"], item["mae"]))

    return diagnostics


def _overall_training_progress(current_model_index: int, total_models: int, fitted: int, total: int) -> int:
    model_start = 18
    model_end = 88
    safe_total_models = max(total_models, 1)
    safe_total_trees = max(total, 1)
    completed_models = max(current_model_index - 1, 0)
    model_fraction = (completed_models + min(max(fitted, 0), safe_total_trees) / safe_total_trees) / safe_total_models
    return int(round(model_start + (model_end - model_start) * model_fraction))


def _normalize_model_label(label: str) -> str:
    if label == "global":
        return "global"
    if label.startswith("type:"):
        return label.split(":", 1)[1]
    return label


def _train_single_model(
    pipeline: Pipeline,
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    X_test: pd.DataFrame,
    y_test: np.ndarray,
    label: str,
    progress_callback: Callable | None = None,
    *,
    target_transform: str = "log_ppm2",
) -> dict:
    preprocessor = pipeline.named_steps["preprocessor"]
    regressor = pipeline.named_steps["regressor"]
    total_trees = regressor.max_iter

    # Target transform: log(price/m²) normalizes the enormous price range
    if target_transform == "log_ppm2":
        size_train = X_train["size_m2"].clip(lower=1).values.astype(float)
        size_test = X_test["size_m2"].clip(lower=1).values.astype(float)
        y_fit = np.log(y_train / size_train)
    elif target_transform == "log_price":
        y_fit = np.log1p(y_train)
    else:
        y_fit = y_train

    # Fit preprocessor ONCE and transform data (TargetEncoder uses y_fit)
    X_train_t = preprocessor.fit_transform(X_train, y_fit)
    X_test_t = preprocessor.transform(X_test)

    use_warm_start = regressor.warm_start

    if use_warm_start:
        # Warm-start loop for progress reporting (global model)
        chunk_size = max(50, total_trees // 20)
        fitted_trees = 0
        while fitted_trees < total_trees:
            next_target = min(fitted_trees + chunk_size, total_trees)
            regressor.max_iter = next_target
            regressor.fit(X_train_t, y_fit)
            fitted_trees = next_target
            if progress_callback:
                progress_callback(label, fitted_trees, total_trees)
    else:
        # Single fit with early stopping (per-type models)
        regressor.fit(X_train_t, y_fit)
        actual_trees = regressor.n_iter_
        if progress_callback:
            progress_callback(label, actual_trees, total_trees)

    # Inverse transform predictions back to price scale
    y_pred_raw = regressor.predict(X_test_t)
    if target_transform == "log_ppm2":
        y_pred = np.maximum(size_test * np.exp(y_pred_raw), 0)
    elif target_transform == "log_price":
        y_pred = np.maximum(np.expm1(y_pred_raw), 0)
    else:
        y_pred = y_pred_raw
    metrics = _compute_metrics(y_test, y_pred)
    metrics["n_train"] = len(X_train)
    metrics["n_test"] = len(X_test)

    importance = {}
    try:
        feat_names = preprocessor.get_feature_names_out()
        try:
            importance_sample_size = min(len(X_test_t), 5000)
            if len(X_test_t) > importance_sample_size:
                sample_idx = np.random.default_rng(42).choice(len(X_test_t), size=importance_sample_size, replace=False)
                X_importance = X_test_t[sample_idx]
                y_importance = y_test[sample_idx]
                size_importance = X_test["size_m2"].clip(lower=1).values.astype(float)[sample_idx]
            else:
                X_importance = X_test_t
                y_importance = y_test
                size_importance = X_test["size_m2"].clip(lower=1).values.astype(float)

            # Permutation importance must use the same target space as the regressor
            if target_transform == "log_ppm2":
                y_importance = np.log(y_importance / size_importance)
            elif target_transform == "log_price":
                y_importance = np.log1p(y_importance)

            perm = permutation_importance(
                regressor,
                X_importance,
                y_importance,
                n_repeats=2,
                random_state=42,
                n_jobs=1,
            )
            importances = perm.importances_mean
        except Exception:
            importances = regressor.feature_importances_
        importance = dict(zip([str(n) for n in feat_names], [float(v) for v in importances], strict=False))
    except Exception:
        pass

    return {"metrics": metrics, "importance": importance}


def _predict_combined_routed(
    X_test: pd.DataFrame,
    global_pipeline: Pipeline,
    per_type_models: dict[str, dict[str, Any]],
    *,
    target_transform: str = "log_ppm2",
) -> np.ndarray:
    size_vals = X_test["size_m2"].clip(lower=1).values.astype(float)

    y_pred_raw = global_pipeline.predict(X_test)
    if target_transform == "log_ppm2":
        y_pred = np.maximum(size_vals * np.exp(y_pred_raw), 0)
    elif target_transform == "log_price":
        y_pred = np.maximum(np.expm1(y_pred_raw), 0)
    else:
        y_pred = y_pred_raw

    if not per_type_models or "property_type" not in X_test.columns:
        return y_pred

    property_types = X_test["property_type"].astype(str)
    for ptype, model_meta in per_type_models.items():
        mask = property_types == ptype
        if not mask.any():
            continue
        X_sub = X_test.loc[mask]
        pt_raw = model_meta["pipeline"].predict(X_sub)
        if target_transform == "log_ppm2":
            pt_size = X_sub["size_m2"].clip(lower=1).values.astype(float)
            pt_pred = np.maximum(pt_size * np.exp(pt_raw), 0)
        elif target_transform == "log_price":
            pt_pred = np.maximum(np.expm1(pt_raw), 0)
        else:
            pt_pred = pt_raw
        y_pred[mask.to_numpy()] = pt_pred

    return y_pred


def train_from_csv(
    csv_path: str,
    progress_callback: Callable | None = None,
    status_callback: Callable | None = None,
) -> dict[str, Any]:
    """Train per-type + global models from a training CSV. Returns model metadata."""
    start = time.time()

    def emit_status(stage: str, progress: int, **extra):
        if status_callback:
            status_callback(
                stage=stage,
                progress=progress,
                elapsed_sec=round(time.time() - start, 2),
                **extra,
            )

    emit_status("dataset_load", 2)
    df = read_csv_flexible(csv_path)
    emit_status("feature_prep", 8, rows=len(df))
    df = enrich_training_df(df)

    # Clean price
    df["price_eur"] = pd.to_numeric(df.get("price_eur"), errors="coerce")
    df = df.dropna(subset=["price_eur"])
    df = df[df["price_eur"] > 0]

    # Exclude non-predictable types
    if "property_type" in df.columns:
        df = df[~df["property_type"].isin(EXCLUDED_PROPERTY_TYPES)]

    # Ensure size_m2 is numeric and positive (required for log_ppm2 target transform)
    df["size_m2"] = pd.to_numeric(df.get("size_m2"), errors="coerce")
    df = df[df["size_m2"] > 0]

    # ── Mixed-type deal contamination removal ──────────────────────────
    # When a deal has multiple property types and prices are pro-rated by area,
    # each part gets the same €/m² regardless of type (e.g., garage gets apartment
    # ppm2). Remove these contaminated rows.
    n_before_deal_clean = len(df)
    if "deal_id" in df.columns and "property_type" in df.columns:
        df["_ppm2_tmp"] = df["price_eur"] / df["size_m2"]
        deal_type_count = df.groupby("deal_id")["property_type"].transform("nunique")
        deal_ppm2_nunique = df.groupby("deal_id")["_ppm2_tmp"].transform("nunique")
        # Mixed-type deal where all parts have identical ppm2 = pro-rated
        contaminated = (deal_type_count > 1) & (deal_ppm2_nunique == 1)
        df = df[~contaminated]
        df = df.drop(columns=["_ppm2_tmp"])
        logger.info("Mixed-type deal cleaning: %d → %d rows", n_before_deal_clean, len(df))

    # ── Global IQR-based outlier removal PER TYPE before train/test split ─
    # Removes extreme log(ppm2) values per type so both train AND test sets
    # are clean. Uses 2.5×IQR fence which removes ~0.3-1.5% per type.
    n_before_global_outlier = len(df)
    if "property_type" in df.columns:
        df["_log_ppm2_tmp"] = np.log(df["price_eur"] / df["size_m2"])
        keep_mask = pd.Series(True, index=df.index)
        for ptype in df["property_type"].unique():
            type_mask = df["property_type"] == ptype
            lp = df.loc[type_mask, "_log_ppm2_tmp"]
            q1, q3 = lp.quantile(0.25), lp.quantile(0.75)
            iqr = q3 - q1
            fence_lo, fence_hi = q1 - 2.5 * iqr, q3 + 2.5 * iqr
            type_outlier = type_mask & ((df["_log_ppm2_tmp"] < fence_lo) | (df["_log_ppm2_tmp"] > fence_hi))
            keep_mask = keep_mask & ~type_outlier
        df = df[keep_mask]
        df = df.drop(columns=["_log_ppm2_tmp"])
        logger.info("Global outlier removal: %d → %d rows", n_before_global_outlier, len(df))

    # ── Spatial distance features from ETRS89/TM coordinates ───────────
    # These are metric coordinates, so Euclidean distance gives meters.
    _LJ_E, _LJ_N = 461000, 100000  # Ljubljana
    _MB_E, _MB_N = 553000, 155000  # Maribor
    _KP_E, _KP_N = 404000, 44000   # Koper (coast)
    lon = pd.to_numeric(df.get("longitude"), errors="coerce")
    lat = pd.to_numeric(df.get("latitude"), errors="coerce")
    df["dist_ljubljana"] = np.sqrt((lon - _LJ_E) ** 2 + (lat - _LJ_N) ** 2)
    df["dist_maribor"] = np.sqrt((lon - _MB_E) ** 2 + (lat - _MB_N) ** 2)
    df["dist_coast"] = np.sqrt((lon - _KP_E) ** 2 + (lat - _KP_N) ** 2)

    y = df["price_eur"].values
    X = df.drop(columns=["price_eur"], errors="ignore")

    # Force all NUMERIC_FEATURES columns to proper numeric dtype
    # (enrichment columns may arrive as mixed str/float from CSV)
    for col in NUMERIC_FEATURES:
        if col in X.columns:
            X[col] = pd.to_numeric(X[col], errors="coerce")

    emit_status("feature_prep", 14, rows=len(df))

    # Stratified split preserves type distribution in train and test sets
    stratify_col = X["property_type"] if "property_type" in X.columns else None
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=stratify_col,
    )
    emit_status("training_setup", 18, rows=len(df))

    # Compute group medians from TRAINING SET ONLY (prevent data leakage)
    train_with_price = X_train.copy()
    train_with_price["price_eur"] = y_train
    valid = train_with_price[train_with_price["size_m2"] > 0].copy()
    valid["ppm2"] = valid["price_eur"] / valid["size_m2"]

    region_medians = (
        valid.groupby("statistical_region")["ppm2"].median().to_dict() if "statistical_region" in valid.columns else {}
    )
    type_medians = valid.groupby("property_type")["ppm2"].median().to_dict() if "property_type" in valid.columns else {}
    global_median_ppm2 = float(valid["ppm2"].median()) if len(valid) > 0 else 2000.0

    # Municipality-level price medians (finer granularity than region)
    municipality_medians: dict[str, float] = {}
    if "municipality_normalized" in valid.columns:
        muni_groups = valid.groupby("municipality_normalized")["ppm2"]
        for muni, group in muni_groups:
            if len(group) >= 10:
                municipality_medians[str(muni)] = float(group.median())
            else:
                # Fall back to region median for small municipalities
                region = valid.loc[group.index, "statistical_region"].mode()
                region_key = region.iloc[0] if len(region) > 0 else "neznana"
                municipality_medians[str(muni)] = region_medians.get(region_key, global_median_ppm2)

    # Apply to train and test sets separately
    X_train["price_per_m2_region"] = (
        X_train.get("statistical_region", pd.Series()).map(region_medians).fillna(global_median_ppm2)
    )
    X_train["price_per_m2_type"] = (
        X_train.get("property_type", pd.Series()).map(type_medians).fillna(global_median_ppm2)
    )
    X_train["price_per_m2_municipality"] = (
        X_train.get("municipality_normalized", pd.Series()).map(municipality_medians).fillna(global_median_ppm2)
    )
    X_test["price_per_m2_region"] = (
        X_test.get("statistical_region", pd.Series()).map(region_medians).fillna(global_median_ppm2)
    )
    X_test["price_per_m2_type"] = X_test.get("property_type", pd.Series()).map(type_medians).fillna(global_median_ppm2)
    X_test["price_per_m2_municipality"] = (
        X_test.get("municipality_normalized", pd.Series()).map(municipality_medians).fillna(global_median_ppm2)
    )

    # ── Type-specific comparable-sales features ────────────────────────
    # Median log(ppm2) per type+municipality, type+KO, and type+EMV zone.
    # These are "comp features" — the strongest location-based price signals.
    valid["log_ppm2"] = np.log(valid["ppm2"].clip(lower=0.01))
    type_muni_comp: dict[str, dict[str, float]] = {}
    type_ko_comp: dict[str, dict[str, float]] = {}
    type_zone_comp: dict[str, dict[str, float]] = {}
    type_naselje_comp: dict[str, dict[str, float]] = {}
    if "property_type" in valid.columns:
        for ptype_grp, ptype_data in valid.groupby("property_type"):
            ptype_key = str(ptype_grp)
            type_median_log = float(ptype_data["log_ppm2"].median())
            # Municipality comp
            muni_med = {}
            if "municipality_normalized" in ptype_data.columns:
                for muni, mgrp in ptype_data.groupby("municipality_normalized"):
                    muni_med[str(muni)] = float(mgrp["log_ppm2"].median()) if len(mgrp) >= 5 else type_median_log
            type_muni_comp[ptype_key] = muni_med
            # KO comp (finer spatial granularity)
            ko_med = {}
            if "ime_ko" in ptype_data.columns:
                for ko, kgrp in ptype_data.groupby("ime_ko"):
                    ko_med[str(ko)] = float(kgrp["log_ppm2"].median()) if len(kgrp) >= 5 else type_median_log
            type_ko_comp[ptype_key] = ko_med
            # EMV zone comp (finest spatial granularity — valuation zone)
            zone_med = {}
            if "emv_zone_name" in ptype_data.columns:
                for zone, zgrp in ptype_data.groupby("emv_zone_name"):
                    if str(zone) != "unknown" and len(zgrp) >= 3:
                        zone_med[str(zone)] = float(zgrp["log_ppm2"].median())
            type_zone_comp[ptype_key] = zone_med
            # Naselje comp
            naselje_med = {}
            if "naselje" in ptype_data.columns:
                for nas, ngrp in ptype_data.groupby("naselje"):
                    if str(nas) != "unknown" and len(ngrp) >= 5:
                        naselje_med[str(nas)] = float(ngrp["log_ppm2"].median())
            type_naselje_comp[ptype_key] = naselje_med

    # Apply comp features to train and test
    global_log_ppm2 = float(valid["log_ppm2"].median()) if len(valid) > 0 else np.log(2000.0)
    for split_X in (X_train, X_test):
        comp_muni_vals = np.full(len(split_X), global_log_ppm2)
        comp_ko_vals = np.full(len(split_X), global_log_ppm2)
        comp_zone_vals = np.full(len(split_X), np.nan)
        comp_naselje_vals = np.full(len(split_X), np.nan)
        if "property_type" in split_X.columns:
            for ptype_key, muni_map in type_muni_comp.items():
                mask = split_X["property_type"] == ptype_key
                if mask.any() and muni_map:
                    comp_muni_vals[mask.values] = (
                        split_X.loc[mask, "municipality_normalized"]
                        .map(muni_map)
                        .fillna(global_log_ppm2)
                        .values
                    )
            for ptype_key, ko_map in type_ko_comp.items():
                mask = split_X["property_type"] == ptype_key
                if mask.any() and ko_map and "ime_ko" in split_X.columns:
                    comp_ko_vals[mask.values] = (
                        split_X.loc[mask, "ime_ko"].map(ko_map).fillna(global_log_ppm2).values
                    )
            for ptype_key, zone_map in type_zone_comp.items():
                mask = split_X["property_type"] == ptype_key
                if mask.any() and zone_map and "emv_zone_name" in split_X.columns:
                    comp_zone_vals[mask.values] = (
                        split_X.loc[mask, "emv_zone_name"].map(zone_map).values
                    )
            for ptype_key, naselje_map in type_naselje_comp.items():
                mask = split_X["property_type"] == ptype_key
                if mask.any() and naselje_map and "naselje" in split_X.columns:
                    comp_naselje_vals[mask.values] = (
                        split_X.loc[mask, "naselje"].map(naselje_map).values
                    )
        split_X["comp_type_muni_ppm2"] = comp_muni_vals
        split_X["comp_type_ko_ppm2"] = comp_ko_vals
        split_X["comp_type_zone_ppm2"] = comp_zone_vals
        split_X["comp_type_naselje_ppm2"] = comp_naselje_vals

    global_num, global_cat = _filter_features(X_train, NUMERIC_FEATURES, CATEGORICAL_FEATURES)
    data_preparation = load_training_metadata(csv_path)

    # Global model
    model_start_times: dict[str, float] = {}
    global_pipeline = _build_pipeline(global_num, global_cat, len(X_train))
    per_type_models: dict[str, Pipeline] = {}
    per_type_metrics: dict[str, dict] = {}
    per_type_feature_usage: dict[str, dict[str, Any]] = {}

    eligible: list[str] = []
    if "property_type" in X_train.columns:
        type_counts = X_train["property_type"].value_counts()
        eligible = type_counts[type_counts >= MIN_SAMPLES_PER_TYPE].index.tolist()

    total_models = 1 + len(eligible)

    def training_progress(label: str, fitted_trees: int, total_trees: int):
        if progress_callback:
            progress_callback(label, fitted_trees, total_trees)

        current_model = _normalize_model_label(label)
        current_index = 1 if label == "global" else eligible.index(current_model) + 2
        now = time.time()
        model_started = model_start_times.setdefault(label, now)
        model_elapsed = max(now - model_started, 0.001)
        trees_per_sec = fitted_trees / model_elapsed if fitted_trees > 0 else None
        eta_sec = ((total_trees - fitted_trees) / trees_per_sec) if trees_per_sec else None
        emit_status(
            "global_model" if label == "global" else "per_type_models",
            _overall_training_progress(current_index, total_models, fitted_trees, total_trees),
            rows=len(df),
            current_model=current_model,
            current_model_index=current_index,
            total_models=total_models,
            current_model_progress=int(round((fitted_trees / max(total_trees, 1)) * 100)),
            fitted_trees=fitted_trees,
            total_trees=total_trees,
            eta_sec=round(float(eta_sec), 2) if eta_sec is not None else None,
            trees_per_sec=round(float(trees_per_sec), 2) if trees_per_sec is not None else None,
        )

    emit_status(
        "global_model",
        18,
        rows=len(df),
        current_model="global",
        current_model_index=1,
        total_models=total_models,
        current_model_progress=0,
        fitted_trees=0,
        total_trees=global_pipeline.named_steps["regressor"].max_iter,
    )
    global_result = _train_single_model(
        global_pipeline,
        X_train,
        y_train,
        X_test,
        y_test,
        "global",
        training_progress,
        target_transform="log_ppm2",
    )

    # Per-type models — signal-scored features + early stopping + aggressive outlier removal
    if eligible:
        for ptype in eligible:
            mask_train = X_train["property_type"] == ptype
            mask_test = X_test["property_type"] == ptype
            Xt = X_train[mask_train].copy()
            yt = y_train[mask_train].copy()
            Xte = X_test[mask_test].copy()
            yte = y_test[mask_test]

            if len(Xte) < 10:
                continue

            # ── Per-type outlier removal in log(ppm2) space ──────────────
            # IQR-based: removes heavy tails that survived global cleanup
            n_before = len(yt)
            size_vals = pd.to_numeric(Xt.get("size_m2"), errors="coerce").clip(lower=1).values
            log_ppm2 = np.log(yt / size_vals)
            q1, q3 = np.percentile(log_ppm2, [25, 75])
            iqr = q3 - q1
            # Tighter fence for large types (1.8×IQR), relaxed for small (2.2×IQR)
            iqr_mult = 1.8 if n_before > 5000 else 2.2
            lo, hi = q1 - iqr_mult * iqr, q3 + iqr_mult * iqr
            outlier_mask = (log_ppm2 >= lo) & (log_ppm2 <= hi)
            if outlier_mask.sum() >= MIN_SAMPLES_PER_TYPE:
                Xt = Xt[outlier_mask]
                yt = yt[outlier_mask]
                logger.info("Type %s: outlier removal %d → %d rows", ptype, n_before, len(yt))

            # Look up type-specific feature config, fall back to global defaults
            type_config = TYPE_FEATURE_CONFIGS.get(ptype, {})
            always_num = type_config.get("always_numeric", ALWAYS_INCLUDE_NUMERIC)
            always_cat = type_config.get("always_categorical", ALWAYS_INCLUDE_CATEGORICAL)

            # Adaptive max extras based on dataset size
            max_extra_num, max_extra_cat = _adaptive_max_extras(len(Xt))

            # Signal-scored feature selection for ALL types
            pt_num, pt_cat, pt_scores = _select_type_specific_features(
                Xt,
                yt,
                PERTYPE_NUMERIC,
                PERTYPE_CATEGORICAL,
                always_numeric=always_num,
                always_categorical=always_cat,
                max_extra_numeric=max_extra_num,
                max_extra_categorical=max_extra_cat,
            )
            selection_mode = f"signal_scored_{ptype}"

            # Per-type models: use early_stopping (no warm_start) for proper regularization
            pt_pipeline = _build_pipeline(pt_num, pt_cat, len(Xt), use_early_stopping=True)
            emit_status(
                "per_type_models",
                _overall_training_progress(
                    eligible.index(ptype) + 2, total_models, 0, pt_pipeline.named_steps["regressor"].max_iter
                ),
                rows=len(df),
                current_model=str(ptype),
                current_model_index=eligible.index(ptype) + 2,
                total_models=total_models,
                current_model_progress=0,
                fitted_trees=0,
                total_trees=pt_pipeline.named_steps["regressor"].max_iter,
            )
            pt_result = _train_single_model(
                pt_pipeline,
                Xt,
                yt,
                Xte,
                yte,
                f"type:{ptype}",
                training_progress,
                target_transform="log_ppm2",
            )
            per_type_models[ptype] = {
                "pipeline": pt_pipeline,
                "numeric_features": pt_num,
                "categorical_features": pt_cat,
            }
            per_type_metrics[ptype] = pt_result["metrics"]
            per_type_feature_usage[ptype] = {
                "numeric_features": pt_num,
                "categorical_features": pt_cat,
                "selection_mode": selection_mode,
            }
            if pt_scores:
                per_type_feature_usage[ptype]["feature_scores"] = {
                    key: round(float(value), 6)
                    for key, value in sorted(pt_scores.items(), key=lambda item: item[1], reverse=True)
                }
    else:
        emit_status("per_type_models", 88, rows=len(df), total_models=total_models)

    # Per-region metrics (not separate models)
    emit_status("evaluation", 92, rows=len(df), total_models=total_models)
    per_region_metrics: dict[str, dict] = {}
    if "statistical_region" in X_test.columns:
        size_test_vals = X_test["size_m2"].clip(lower=1).values.astype(float)
        y_pred_all_raw = global_pipeline.predict(X_test)
        y_pred_all = np.maximum(size_test_vals * np.exp(y_pred_all_raw), 0)
        for region in X_test["statistical_region"].unique():
            mask = X_test["statistical_region"] == region
            if mask.sum() >= 10:
                per_region_metrics[str(region)] = _compute_metrics(y_test[mask], y_pred_all[mask])

    # Combined routing metrics: use per-type model when available, else global
    if per_type_models:
        y_pred_combined = _predict_combined_routed(
            X_test, global_pipeline, per_type_models, target_transform="log_ppm2"
        )
        combined_metrics = _compute_metrics(y_test, y_pred_combined)
    else:
        size_test_combined = X_test["size_m2"].clip(lower=1).values.astype(float)
        y_pred_combined_raw = global_pipeline.predict(X_test)
        y_pred_combined = np.maximum(size_test_combined * np.exp(y_pred_combined_raw), 0)
        combined_metrics = global_result["metrics"]

    segment_diagnostics = _build_segment_diagnostics(X_test, y_test, y_pred_combined)

    # ── EV baseline comparison ─────────────────────────────────────────
    ev_baseline_metrics = None
    ev_benchmark_col = "ev_benchmark_price_eur"
    if ev_benchmark_col in X_test.columns:
        ev_vals = pd.to_numeric(X_test[ev_benchmark_col], errors="coerce")
        ev_mask = ev_vals.notna() & (ev_vals > 0)
        coverage_rows = int(ev_mask.sum())
        if coverage_rows >= 10:
            ev_pred = ev_vals[ev_mask].values
            ev_actual = y_test[ev_mask.values]
            benchmark_m = _compute_metrics(ev_actual, ev_pred)
            model_m = _compute_metrics(ev_actual, y_pred_combined[ev_mask.values])
            delta = {}
            for k in ("r2", "mae", "rmse", "mape", "median_ae"):
                bv = benchmark_m.get(k)
                mv = model_m.get(k)
                if bv is not None and mv is not None:
                    delta[k] = round(mv - bv, 6)
            ev_baseline_metrics = {
                "coverage_rows": coverage_rows,
                "benchmark_metrics": benchmark_m,
                "model_metrics_on_coverage": model_m,
                "delta_vs_model": delta,
            }

    # ── Variant benchmarks & matrix ────────────────────────────────────
    variant_benchmarks: dict[str, Any] = {}
    variant_matrix: dict[str, Any] = {}
    for variant_name, enabled_sources in _VARIANT_CONFIGS.items():
        v_num = _filter_features_by_source(global_num, enabled_sources)
        v_cat = _filter_features_by_source(global_cat, enabled_sources)
        if not v_num:
            v_num = [f for f in global_num if not any(f.startswith(p) for ps in _ENRICHMENT_PREFIXES.values() for p in ps)]
        if not v_num:
            continue
        # Lightweight global model for this variant
        v_pipeline = _build_pipeline(v_num, v_cat, len(X_train), use_early_stopping=True)
        v_reg = v_pipeline.named_steps["regressor"]
        v_reg.max_iter = max(100, v_reg.max_iter // 4)
        v_reg.n_iter_no_change = 15
        v_result = _train_single_model(
            v_pipeline, X_train, y_train, X_test, y_test,
            f"variant:{variant_name}", None, target_transform="log_ppm2",
        )
        variant_benchmarks[variant_name] = {
            "label": variant_name,
            "variant_label": variant_name,
            "enabled_sources": enabled_sources,
            "metrics": v_result["metrics"],
        }
        # Full-global delta
        if variant_name != "full_global" and "full_global" in variant_benchmarks:
            fg = variant_benchmarks["full_global"]["metrics"]
            vm = v_result["metrics"]
            variant_benchmarks[variant_name]["delta_vs_full_global"] = {
                k: round(vm.get(k, 0) - fg.get(k, 0), 6)
                for k in ("r2", "mae", "rmse", "mape")
                if k in vm and k in fg
            }
        # Variant matrix entry: per-type metrics with lightweight per-type models
        v_pt_models: dict[str, dict] = {}
        v_pt_metrics: dict[str, dict] = {}
        if eligible:
            for ptype in eligible:
                mask_tr = X_train["property_type"] == ptype
                mask_te = X_test["property_type"] == ptype
                Xvt = X_train[mask_tr]
                yvt = y_train[mask_tr]
                Xvte = X_test[mask_te]
                yvte = y_test[mask_te]
                if len(Xvte) < 10 or len(Xvt) < MIN_SAMPLES_PER_TYPE:
                    continue
                vpt_num = _filter_features_by_source(
                    [f for f in PERTYPE_NUMERIC if f in Xvt.columns], enabled_sources
                )
                vpt_cat = _filter_features_by_source(
                    [f for f in PERTYPE_CATEGORICAL if f in Xvt.columns], enabled_sources
                )
                vpt_num, vpt_cat = _filter_features(Xvt, vpt_num, vpt_cat)
                if not vpt_num:
                    continue
                vpt_pipe = _build_pipeline(vpt_num, vpt_cat, len(Xvt), use_early_stopping=True)
                vpt_reg = vpt_pipe.named_steps["regressor"]
                vpt_reg.max_iter = max(100, vpt_reg.max_iter // 4)
                vpt_reg.n_iter_no_change = 15
                vpt_res = _train_single_model(
                    vpt_pipe, Xvt, yvt, Xvte, yvte,
                    f"variant:{variant_name}:{ptype}", None, target_transform="log_ppm2",
                )
                v_pt_models[ptype] = {"pipeline": vpt_pipe}
                v_pt_metrics[ptype] = vpt_res["metrics"]
        # Combined variant metrics
        if v_pt_models:
            y_var_combined = _predict_combined_routed(
                X_test, v_pipeline, v_pt_models, target_transform="log_ppm2"
            )
            v_combined_m = _compute_metrics(y_test, y_var_combined)
        else:
            v_combined_m = v_result["metrics"]
        variant_matrix[variant_name] = {
            "label": variant_name,
            "variant_label": variant_name,
            "enabled_sources": enabled_sources,
            "global_metrics": v_result["metrics"],
            "combined_metrics": v_combined_m,
            "per_type_metrics": v_pt_metrics,
            "per_type_count": len(v_pt_models),
        }

    # Production combined entry in variant_benchmarks
    variant_benchmarks["production_combined"] = {
        "label": "production_combined",
        "variant_label": "production_combined",
        "enabled_sources": {s: True for s in _ENRICHMENT_PREFIXES},
        "metrics": combined_metrics,
    }

    # Municipality coordinates
    emit_status("artifact_save", 96, rows=len(df), total_models=total_models)
    coords_by_municipality: dict[str, dict] = {}
    coord_key = "municipality_normalized" if "municipality_normalized" in df.columns else "municipality"
    for col_pair in [(coord_key, "latitude", "longitude")]:
        if all(c in df.columns for c in col_pair):
            for mun, grp in df.groupby(col_pair[0]):
                lat = grp[col_pair[1]].median()
                lon = grp[col_pair[2]].median()
                if pd.notna(lat) and pd.notna(lon):
                    coords_by_municipality[str(mun)] = {
                        "lat": float(lat),
                        "lon": float(lon),
                    }

    duration = time.time() - start

    # Save artifact
    os.makedirs(MODEL_DIR, exist_ok=True)
    emit_status("finalizing", 99, rows=len(df), total_models=total_models)
    artifact = {
        "version": "7.2",
        "target_transform": "log_ppm2",
        "log_target": True,  # backward compat
        "global_model": {
            "pipeline": global_pipeline,
            "numeric_features": global_num,
            "categorical_features": global_cat,
        },
        # Backward compat
        "global_pipeline": global_pipeline,
        "per_type_models": per_type_models,
        "region_medians": region_medians,
        "type_medians": type_medians,
        "municipality_medians": municipality_medians,
        "global_median_ppm2": global_median_ppm2,
        "type_muni_comp": type_muni_comp,
        "type_ko_comp": type_ko_comp,
        "type_zone_comp": type_zone_comp,
        "type_naselje_comp": type_naselje_comp,
        "global_log_ppm2": global_log_ppm2,
        "global_metrics": global_result["metrics"],
        "global_importance": global_result["importance"],
        "per_type_metrics": per_type_metrics,
        "per_region_metrics": per_region_metrics,
        "combined_metrics": combined_metrics,
        "coords_by_municipality": coords_by_municipality,
        "feature_labels": FEATURE_LABELS_SL,
        "trained_at": pd.Timestamp.now().isoformat(),
        "csv_path": csv_path,
        "rows": len(df),
        "train_rows": len(X_train),
        "test_rows": len(X_test),
        "used_features": global_num + global_cat,
        "per_type_features": per_type_feature_usage,
        "data_preparation": data_preparation,
        "segment_diagnostics": segment_diagnostics,
        "ev_baseline_metrics": ev_baseline_metrics,
        "variant_benchmarks": variant_benchmarks,
        "variant_matrix": variant_matrix,
        "model_type": "HistGradientBoostingRegressor",
        "duration_sec": duration,
    }
    model_path = os.path.join(MODEL_DIR, "price_model.joblib")
    joblib.dump(artifact, model_path, compress=3)

    return {
        "model_path": model_path,
        "csv_path": csv_path,
        "rows": len(df),
        "duration_sec": round(duration, 2),
        "global_metrics": global_result["metrics"],
        "global_importance": global_result["importance"],
        "per_type_metrics": per_type_metrics,
        "per_region_metrics": per_region_metrics,
        "combined_metrics": combined_metrics,
        "per_type_count": len(per_type_models),
        "used_features": global_num + global_cat,
        "per_type_features": per_type_feature_usage,
        "data_preparation": data_preparation,
        "segment_diagnostics": segment_diagnostics,
        "ev_baseline_metrics": ev_baseline_metrics,
        "variant_benchmarks": variant_benchmarks,
        "variant_matrix": variant_matrix,
        "model_type": "HistGradientBoostingRegressor",
    }


def load_model() -> dict | None:
    """Load model artifact, auto-reloading when the file changes on disk.

    The ARQ worker trains in a separate process, so `invalidate_model_cache()`
    only clears the worker's cache. This mtime check ensures the API process
    picks up the new model without requiring a restart.
    """
    global _model_cache, _model_cache_mtime
    model_path = os.path.join(MODEL_DIR, "price_model.joblib")
    if not os.path.exists(model_path):
        return None
    current_mtime = os.path.getmtime(model_path)
    if _model_cache is not None and current_mtime == _model_cache_mtime:
        return _model_cache
    _model_cache = joblib.load(model_path)
    _model_cache_mtime = current_mtime
    return _model_cache


def invalidate_model_cache() -> None:
    """Clear the in-process model cache (call after training a new model)."""
    global _model_cache, _model_cache_mtime
    _model_cache = None
    _model_cache_mtime = 0.0


def _coerce_binary(value: Any, default: int = 0) -> int:
    """Coerce a value to a binary 0/1 flag."""
    if value is None:
        return default
    if isinstance(value, float) and np.isnan(value):
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, str):
        low = value.strip().lower()
        if low in {"1", "true", "yes", "da"}:
            return 1
        if low in {"0", "false", "no", "ne", ""}:
            return 0
    try:
        fval = float(value)
        if np.isnan(fval):
            return default
        return 1 if fval > 0 else 0
    except (TypeError, ValueError):
        return default


def _build_normalized_payload(
    payload: dict[str, Any],
    numeric_features: list[str],
    categorical_features: list[str],
    artifact: dict[str, Any],
) -> dict[str, Any]:
    """Build a normalized input row for prediction, including derived features and imputation."""
    from app.services.regions_service import lookup_region, normalize

    coords_by_muni = artifact.get("coords_by_municipality", {})
    region_medians = artifact.get("region_medians", {})
    type_medians = artifact.get("type_medians", {})
    global_median = artifact.get("global_median_ppm2", 2000.0)

    row: dict[str, Any] = {}

    # Numeric features
    for col in numeric_features:
        val = payload.get(col)
        if val is None or (isinstance(val, float) and np.isnan(val)):
            row[col] = np.nan
        else:
            try:
                row[col] = float(val)
            except (TypeError, ValueError):
                row[col] = np.nan

    # Categorical features
    for col in categorical_features:
        if col == "municipality_normalized":
            row[col] = normalize_municipality_name(payload.get("municipality"))
            continue
        if col == "statistical_region" and col not in payload:
            muni = normalize_municipality_name(payload.get("municipality"))
            row[col] = lookup_region(muni)
        else:
            val = payload.get(col, "unknown")
            row[col] = normalize(str(val)) if val else "unknown"

    # Derived: building_age
    if "building_age" in numeric_features and "building_age" not in payload:
        yb = payload.get("year_built")
        if yb is not None and not (isinstance(yb, float) and np.isnan(yb)):
            row["building_age"] = float(pd.Timestamp.now().year - int(yb))
        else:
            row["building_age"] = np.nan

    # Derived: log_size_m2
    if "log_size_m2" in numeric_features and "log_size_m2" not in payload:
        sm2 = payload.get("size_m2")
        if sm2 is not None and not (isinstance(sm2, float) and np.isnan(sm2)):
            row["log_size_m2"] = float(np.log1p(max(0, float(sm2))))
        else:
            row["log_size_m2"] = np.nan

    # Binary flags
    for amenity in (
        "novogradnja",
        "has_klet",
        "has_garaza",
        "has_terasa",
        "has_shramba",
        "has_parking",
        "ddv_vkljucen",
        "stavba_je_dokoncana",
    ):
        if amenity in numeric_features:
            default = 1 if amenity == "stavba_je_dokoncana" else 0
            row[amenity] = float(_coerce_binary(payload.get(amenity, default), default=default))

    # num_prostori
    if "num_prostori" in numeric_features:
        val = payload.get("num_prostori", 0)
        try:
            v = float(val)
            row["num_prostori"] = 0.0 if np.isnan(v) else v
        except (TypeError, ValueError):
            row["num_prostori"] = 0.0

    # transaction_year / transaction_quarter
    if "transaction_year" in numeric_features and "transaction_year" not in payload:
        row["transaction_year"] = float(pd.Timestamp.now().year)
    if "transaction_quarter" in numeric_features and "transaction_quarter" not in payload:
        row["transaction_quarter"] = float(pd.Timestamp.now().quarter)

    # Lat/lon imputation from municipality coords
    municipality_norm = normalize_municipality_name(payload.get("municipality"))
    for coord_key in ("latitude", "longitude"):
        val = row.get(coord_key)
        if val is None or (isinstance(val, float) and np.isnan(val)):
            muni_coords = coords_by_muni.get(municipality_norm, {})
            coord_val = muni_coords.get("lat" if coord_key == "latitude" else "lon")
            if coord_val is None:
                coord_val = muni_coords.get(coord_key)
            row[coord_key] = float(coord_val) if coord_val is not None else np.nan

    # Group medians
    if "price_per_m2_region" in numeric_features:
        region = row.get("statistical_region", "neznana")
        row["price_per_m2_region"] = region_medians.get(region, global_median)

    if "price_per_m2_type" in numeric_features:
        ptype = row.get("property_type", "unknown")
        row["price_per_m2_type"] = type_medians.get(ptype, global_median)

    if "price_per_m2_municipality" in numeric_features:
        municipality_medians = artifact.get("municipality_medians", {})
        muni_key = row.get("municipality_normalized", municipality_norm)
        row["price_per_m2_municipality"] = municipality_medians.get(
            muni_key, region_medians.get(row.get("statistical_region", "neznana"), global_median)
        )

    # Distance features (ETRS89/TM coordinates → Euclidean distance in meters)
    _LJ_E, _LJ_N = 461000, 100000
    _MB_E, _MB_N = 553000, 155000
    _KP_E, _KP_N = 404000, 44000
    lon_val = row.get("longitude", np.nan)
    lat_val = row.get("latitude", np.nan)
    if "dist_ljubljana" in numeric_features:
        if not (isinstance(lon_val, float) and np.isnan(lon_val)):
            row["dist_ljubljana"] = float(np.sqrt((lon_val - _LJ_E) ** 2 + (lat_val - _LJ_N) ** 2))
        else:
            row["dist_ljubljana"] = np.nan
    if "dist_maribor" in numeric_features:
        if not (isinstance(lon_val, float) and np.isnan(lon_val)):
            row["dist_maribor"] = float(np.sqrt((lon_val - _MB_E) ** 2 + (lat_val - _MB_N) ** 2))
        else:
            row["dist_maribor"] = np.nan
    if "dist_coast" in numeric_features:
        if not (isinstance(lon_val, float) and np.isnan(lon_val)):
            row["dist_coast"] = float(np.sqrt((lon_val - _KP_E) ** 2 + (lat_val - _KP_N) ** 2))
        else:
            row["dist_coast"] = np.nan

    # Type-specific comparable-sales features
    global_log_ppm2 = artifact.get("global_log_ppm2", np.log(2000.0))
    ptype_key = payload.get("property_type", "unknown")
    if "comp_type_muni_ppm2" in numeric_features:
        type_muni_comp = artifact.get("type_muni_comp", {})
        muni_map = type_muni_comp.get(ptype_key, {})
        muni_key = row.get("municipality_normalized", municipality_norm)
        row["comp_type_muni_ppm2"] = muni_map.get(muni_key, global_log_ppm2)
    if "comp_type_ko_ppm2" in numeric_features:
        type_ko_comp = artifact.get("type_ko_comp", {})
        ko_map = type_ko_comp.get(ptype_key, {})
        ko_key = payload.get("ime_ko", "unknown")
        row["comp_type_ko_ppm2"] = ko_map.get(str(ko_key), global_log_ppm2)
    if "comp_type_zone_ppm2" in numeric_features:
        type_zone_comp = artifact.get("type_zone_comp", {})
        zone_map = type_zone_comp.get(ptype_key, {})
        zone_key = payload.get("emv_zone_name", "unknown")
        row["comp_type_zone_ppm2"] = zone_map.get(str(zone_key), np.nan)
    if "comp_type_naselje_ppm2" in numeric_features:
        type_naselje_comp = artifact.get("type_naselje_comp", {})
        naselje_map = type_naselje_comp.get(ptype_key, {})
        naselje_key = payload.get("naselje", "unknown")
        row["comp_type_naselje_ppm2"] = naselje_map.get(str(naselje_key), np.nan)

    return row


def predict_one(features: dict[str, Any]) -> dict[str, Any]:
    """Predict price for a single property."""
    artifact = load_model()
    if artifact is None:
        raise RuntimeError("No trained model found. Train a model first.")

    from app.services.regions_service import normalize

    ptype = normalize(str(features.get("property_type", "unknown")))

    # Route to per-type model or global
    per_type_models = artifact.get("per_type_models", {})
    global_model = artifact.get("global_model", {})

    if ptype in per_type_models:
        tm = per_type_models[ptype]
        if isinstance(tm, dict) and "pipeline" in tm:
            pipeline = tm["pipeline"]
            num_feats = tm["numeric_features"]
            cat_feats = tm["categorical_features"]
        else:
            # Legacy: pipeline stored directly
            pipeline = tm
            num_feats = PERTYPE_NUMERIC
            cat_feats = PERTYPE_CATEGORICAL
        model_used = f"per_type:{ptype}"
    elif global_model and "pipeline" in global_model:
        pipeline = global_model["pipeline"]
        num_feats = global_model["numeric_features"]
        cat_feats = global_model["categorical_features"]
        model_used = "global"
    else:
        pipeline = artifact["global_pipeline"]
        num_feats = NUMERIC_FEATURES
        cat_feats = CATEGORICAL_FEATURES
        model_used = "global"

    normalized = _build_normalized_payload(features, num_feats, cat_feats, artifact)
    row = pd.DataFrame([normalized])
    raw_pred = float(pipeline.predict(row)[0])

    # Inverse transform based on how the model was trained
    target_transform = artifact.get("target_transform")
    if target_transform is None:
        # Backward compat: v5.0 used log_target flag
        target_transform = "log_price" if artifact.get("log_target") else "none"

    if target_transform == "log_ppm2":
        size_m2 = max(float(normalized.get("size_m2", 1.0)), 1.0)
        predicted = max(0.0, size_m2 * float(np.exp(raw_pred)))
    elif target_transform == "log_price":
        predicted = max(0.0, float(np.expm1(raw_pred)))
    else:
        predicted = max(0.0, raw_pred)

    return {
        "predicted_price_eur": round(predicted, 2),
        "model_used": model_used,
        "features_used": {k: str(v) for k, v in normalized.items()},
    }


def get_model_info() -> dict[str, Any] | None:
    """Get metadata about the currently loaded model."""
    artifact = load_model()
    if artifact is None:
        return None
    return {
        "version": artifact.get("version"),
        "trained_at": artifact.get("trained_at"),
        "rows": artifact.get("rows"),
        "train_rows": artifact.get("train_rows"),
        "test_rows": artifact.get("test_rows"),
        "used_features": artifact.get("used_features", []),
        "model_type": artifact.get("model_type", "HistGradientBoostingRegressor"),
        "duration_sec": artifact.get("duration_sec"),
        "global_metrics": artifact.get("global_metrics"),
        "per_type_metrics": artifact.get("per_type_metrics"),
        "per_region_metrics": artifact.get("per_region_metrics"),
        "combined_metrics": artifact.get("combined_metrics"),
        "global_importance": artifact.get("global_importance"),
        "feature_labels": artifact.get("feature_labels"),
        "per_type_features": artifact.get("per_type_features"),
        "per_type_count": len(artifact.get("per_type_models", {})),
        "type_models_trained": sorted(artifact.get("per_type_models", {}).keys()),
        "coords_by_municipality": artifact.get("coords_by_municipality"),
        "csv_path": artifact.get("csv_path"),
        "data_preparation": artifact.get("data_preparation"),
        "segment_diagnostics": artifact.get("segment_diagnostics"),
        "ev_baseline_metrics": artifact.get("ev_baseline_metrics"),
        "variant_benchmarks": artifact.get("variant_benchmarks"),
        "variant_matrix": artifact.get("variant_matrix"),
    }
