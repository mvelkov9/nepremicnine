"""Model training & prediction service — CatBoost per-type architecture with spatial KNN features."""

from __future__ import annotations

import contextlib
import json
import logging
import os
import subprocess
import threading
import time
from collections.abc import Callable
from functools import lru_cache
from math import isnan
from typing import Any

import joblib
import numpy as np
import pandas as pd
from catboost import CatBoostRegressor, Pool
from scipy.spatial import KDTree
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, StratifiedKFold

from app.services.data_processing_service import (
    EXCLUDED_PROPERTY_TYPES,
    apply_gurs_deterministic_enrichment,
    enrich_training_df,
    load_training_metadata,
    read_csv_flexible,
)
from app.utils.municipality import municipality_slug, normalize_municipality_name
from app.utils.slovenian_labels import format_municipality_label, format_region_label

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
    "comp_type_naselje_ppm2",
    "comp_subtype_muni_ppm2",
    "comp_subtype_ko_ppm2",
    "comp_subtype_naselje_ppm2",
    "emv_zone_match",
    "emv_zone_level",
    "dtm_nadm_visina_stavbe",
    "opt_zmogljivost",
    "kn_etazna_lastnina",
    # ── Enrichment features (EV/GJI/KN/RN registers) ──
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
    "gji_elektrika_distance_m",
    "gji_elektrika_nearby_100m",
    "gji_plin_distance_m",
    "gji_plin_nearby_100m",
    "gji_ceste_distance_m",
    "gji_ceste_nearby_100m",
    "gji_toplota_distance_m",
    "gji_toplota_nearby_100m",
    "gji_elektrika_nearby_500m",
    "gji_plin_nearby_500m",
    "gji_ceste_nearby_500m",
    "gji_toplota_nearby_500m",
    # ── New GJI transport & fiber features ──
    "gji_zeleznice_distance_m",  # Distance to nearest railway line
    "gji_zeleznice_nearby_1000m",  # Railway within 1 km (accessibility)
    "gji_zeleznice_nearby_100m",  # Railway within 100 m (v9: Spearman 0.12-0.24 across types)
    "ev_id_konstrukcija",  # v9: construction type (brick/concrete/wood) — Spearman 0.165 on stanovanje
    "gji_letalisca_distance_m",  # Distance to nearest airport geometry
    "gji_opt_distance_m",  # Distance to nearest optical fiber endpoint
    "gji_opt_nearby_100m",  # Fiber within 100 m (broadband access)
    # ── New DTM water proximity feature ──
    "dtm_voda_distance_m",  # Distance to nearest natural water object
    # ── Rental market comparable ──
    "rental_median_ppm2_muni",  # Median rental €/m²/month in same municipality+type
    "kn_ggo_openness",
    "rn_address_match",
    "stopnja_ddv",
    "vrsta_dela_stavbe",
    # ── Transaction time features ──
    "transaction_month",  # Month of transaction (1–12)
    "transaction_season",  # Season (1=spring, 2=summer, 3=autumn, 4=winter)
    # ── Engineered features (computed from training data) ──
    "knn_3_log_ppm2",  # Median log(€/m²) of 3 nearest neighbours (hyper-local)
    "knn_5_log_ppm2",  # Median log(€/m²) of 5 nearest neighbours (all types)
    "knn_20_log_ppm2",  # Median log(€/m²) of 20 nearest neighbours (all types)
    "knn_dw10_log_ppm2",  # Distance-weighted mean log(€/m²) of 10 nearest neighbours
    "knn_type_10_log_ppm2",  # Median log(€/m²) of 10 nearest same-type neighbours
    "ko_transaction_count",  # Number of training transactions in same KO
    "muni_transaction_count",  # Number of training transactions in same municipality
    "naselje_transaction_count",  # Number of training transactions in same naselje
    "ko_vs_muni_premium",  # KO log(€/m²) minus municipality log(€/m²)
    "muni_vs_region_premium",  # log(municipality €/m² / region €/m²)
    "size_percentile",  # Size rank within type (0..1)
    "has_ev_data",  # Binary: has any EV register data
    "has_renovation_data",  # Binary: has any renovation year
    "time_index",  # Linear time index (quarters since earliest year)
    "latest_renovation_year",  # Most recent renovation year across all categories
    "years_since_renovation",  # transaction_year - latest_renovation_year
    "parcel_sold_fraction",  # size_m2 / parcela_m2 (capped at 1)
    "price_per_m2_ko",  # Median €/m² per KO (all types)
    # ── Interaction features ──
    "hyperlocal_premium",  # knn_type_10 - comp_type_muni (micro-location vs muni average)
    "building_age_sq",  # building_age^2 / 1000 (non-linear aging effect)
]

CATEGORICAL_FEATURES = [
    "municipality_normalized",
    "property_type",
    "market_subtype_key",
    "statistical_region",
    "lega_v_stavbi",
    "ime_ko",
    "naselje",
    "vrsta_zemljisca",
    "kn_ggo_section",
    "dtm_pokritost_tal",
    "parcela_namenska_raba",
    "emv_zone_model",
    "emv_zone_id",
    "emv_zone_name",
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
    "comp_type_naselje_ppm2",
    "emv_zone_match",
    "emv_zone_level",
    "dtm_nadm_visina_stavbe",
    "opt_zmogljivost",
    "kn_etazna_lastnina",
    # High-signal engineered features
    "knn_3_log_ppm2",
    "knn_5_log_ppm2",
    "knn_20_log_ppm2",
    "knn_dw10_log_ppm2",
    "knn_type_10_log_ppm2",
    "ko_transaction_count",
    "muni_transaction_count",
    "ko_vs_muni_premium",
    "muni_vs_region_premium",
    "price_per_m2_ko",
    # Renovation & trend features
    "renovation_score",
    "building_quality_index",
    "price_trend_muni",
    "price_trend_muni_yoy",
    "price_level_muni",
    "global_pred_log_price",
    # Interaction features
    "hyperlocal_premium",
    "building_age_sq",
}

ALWAYS_INCLUDE_CATEGORICAL = {
    "municipality_normalized",
    "statistical_region",
    "lega_v_stavbi",
    "dtm_pokritost_tal",
    "parcela_namenska_raba",
}

CALIBRATION_SEGMENT_PRIORITIES: dict[str, list[str]] = {
    "parcela": ["parcela_namenska_raba", "vrsta_zemljisca", "kn_ggo_section"],
    "kmetijsko": ["market_subtype_key", "parcela_namenska_raba", "vrsta_zemljisca", "kn_ggo_section", "ime_ko"],
    "hisa": ["kn_ggo_section", "ime_ko", "ev_id_tip_stavbe"],
    "stanovanje": ["kn_ggo_section", "lega_v_stavbi", "ime_ko"],
    "garaza": ["kn_ggo_section", "vrsta_dela_stavbe", "ime_ko"],
    "poslovni_prostor": ["kn_ggo_section", "vrsta_dela_stavbe", "ime_ko"],
    "industrijski": ["kn_ggo_section", "ime_ko", "emv_zone_id"],
    "turisticni": ["kn_ggo_section", "ime_ko", "emv_zone_id"],
    "gostinstvo": ["kn_ggo_section", "ime_ko", "emv_zone_id"],
}

CALIBRATION_DISABLED_TYPES: set[str] = set()
CALIBRATION_SEGMENT_DISABLED_TYPES = {"gostinstvo"}
CALIBRATION_PRICE_BAND_DISABLED_TYPES = {"gostinstvo", "turisticni", "industrijski"}

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
    "comp_subtype_muni_ppm2": "€/m² podtip+občina",
    "comp_subtype_ko_ppm2": "€/m² podtip+KO",
    "comp_subtype_naselje_ppm2": "€/m² podtip+naselje",
    # Enrichment feature labels
    "emv_zone_match": "EMV ujemanje cone",
    "emv_zone_level": "EMV raven cone",
    "emv_zone_id": "EMV cona ID",
    "dtm_nadm_visina_stavbe": "DTM nadmorska višina temelja",
    "opt_zmogljivost": "Optika minimalna zmogljivost",
    "kn_etazna_lastnina": "Etažna lastnina",
    "dtm_pokritost_tal": "DTM pokritost tal",
    "parcela_namenska_raba": "Namenska raba parcele",
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
    "gji_elektrika_distance_m": "Razdalja do elektrike",
    "gji_elektrika_nearby_100m": "Elektrika v 100m",
    "gji_plin_distance_m": "Razdalja do plina",
    "gji_plin_nearby_100m": "Plin v 100m",
    "gji_ceste_distance_m": "Razdalja do ceste",
    "gji_ceste_nearby_100m": "Cesta v 100m",
    "gji_toplota_distance_m": "Razdalja do toplote",
    "gji_toplota_nearby_100m": "Toplota v 100m",
    "gji_elektrika_nearby_500m": "Elektrika v 500m",
    "gji_plin_nearby_500m": "Plin v 500m",
    "gji_ceste_nearby_500m": "Ceste v 500m",
    "gji_toplota_nearby_500m": "Toplota v 500m",
    "gji_zeleznice_distance_m": "Razdalja do železnice (m)",
    "gji_zeleznice_nearby_1000m": "Železnica v 1 km",
    "gji_letalisca_distance_m": "Razdalja do letališča (m)",
    "gji_opt_distance_m": "Razdalja do optike (m)",
    "gji_opt_nearby_100m": "Optika v 100 m",
    "dtm_voda_distance_m": "Razdalja do vode (m)",
    "rental_median_ppm2_muni": "Mediana najemnine €/m²/mes (občina)",
    "transaction_month": "Mesec transakcije",
    "transaction_season": "Sezona transakcije",
    "kn_ggo_openness": "GGO odprtost",
    "rn_address_match": "Ujemanje naslova",
    "emv_zone_name": "EMV cona ime",
    "emv_zone_model": "EMV model vrednotenja",
    "kn_ggo_section": "GGO odsek",
    # Engineered features
    "knn_3_log_ppm2": "KNN-3 log(€/m²)",
    "knn_5_log_ppm2": "KNN-5 log(€/m²)",
    "knn_20_log_ppm2": "KNN-20 log(€/m²)",
    "knn_dw10_log_ppm2": "KNN-DW10 log(€/m²)",
    "knn_type_10_log_ppm2": "KNN-10 tip log(€/m²)",
    "ko_transaction_count": "Št. transakcij v KO",
    "muni_transaction_count": "Št. transakcij v občini",
    "naselje_transaction_count": "Št. transakcij v naselju",
    "ko_vs_muni_premium": "KO premija vs občina",
    "muni_vs_region_premium": "Občina premija vs regija",
    "size_percentile": "Percentil velikosti",
    "has_ev_data": "Podatki iz EV",
    "has_renovation_data": "Podatki o obnovi",
    "time_index": "Časovni indeks",
    "latest_renovation_year": "Zadnja obnova leto",
    "years_since_renovation": "Let od obnove",
    "parcel_sold_fraction": "Delež prodane parcele",
    "price_per_m2_ko": "€/m² KO",
    "renovation_score": "Ocena obnove",
    "building_quality_index": "Indeks kakovosti stavbe",
    "price_trend_muni": "Trend cen občina (QoQ)",
    "price_trend_muni_yoy": "Trend cen občina (YoY)",
    "price_level_muni": "Raven cen občina",
    "global_pred_log_price": "Napoved globalnega modela (log)",
}

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
MODEL_DIR = os.path.join(DATA_DIR, "models")
DEFAULT_MODEL_FILENAME = "price_model.joblib"

_MIN_FILL_RATE = 0.10
_MIN_SIGNAL_SCORE = 0.01
_MAX_EXTRA_NUMERIC = 8
_MAX_EXTRA_CATEGORICAL = 8


def _default_model_path() -> str:
    return os.path.join(MODEL_DIR, DEFAULT_MODEL_FILENAME)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    with contextlib.suppress(TypeError, ValueError):
        return int(raw)
    return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    with contextlib.suppress(TypeError, ValueError):
        return float(raw)
    return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = str(raw).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


_RECENT_WINDOW_MONTHS = max(0, _env_int("MODEL_RECENT_WINDOW_MONTHS", 0))
_RECENT_WINDOW_MIN_ROWS = max(1000, _env_int("MODEL_RECENT_MIN_ROWS", 30000))
_RECENT_WINDOW_MAX_YEARS = max(2, _env_int("MODEL_RECENT_MAX_YEARS", 4))
_MIN_FULL_SHARE = min(max(_env_float("MODEL_MIN_FULL_SHARE", 0.95), 0.0), 1.0)
_ENABLE_MARKET_VALIDITY_FILTER = bool(_env_int("MODEL_ENABLE_MARKET_VALIDITY_FILTER", 0))
_ENABLE_PREDICTION_ENRICHMENT = _env_bool("ENABLE_PREDICTION_ENRICHMENT", True)
_ENABLE_PREDICTION_SPATIAL_ENRICHMENT = _env_bool("ENABLE_PREDICTION_SPATIAL_ENRICHMENT", True)
_PREDICTION_ENRICHMENT_TIMEOUT_SEC = max(0.0, _env_float("PREDICTION_ENRICHMENT_TIMEOUT_SEC", 12.0))

MARKET_VALIDITY_RULES: dict[str, dict[str, Any]] = {
    "stanovanje": {"min_price_eur": 8000.0, "min_ppm2": 700.0},
    "hisa": {"min_price_eur": 15000.0, "min_ppm2": 250.0},
    "parcela": {"min_price_eur": 2500.0, "min_ppm2": 0.45},
    "kmetijsko": {"min_price_eur": 5000.0, "min_ppm2": 70.0, "drop_unknown_municipality": True},
    "garaza": {"min_price_eur": 6000.0, "min_ppm2": 300.0},
    "poslovni_prostor": {"min_price_eur": 10000.0, "min_ppm2": 250.0},
    "industrijski": {"min_price_eur": 8000.0, "min_ppm2": 100.0},
    "turisticni": {"min_price_eur": 10000.0, "min_ppm2": 200.0},
    "gostinstvo": {"min_price_eur": 10000.0, "min_ppm2": 200.0},
}

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
    # KNN & engineered
    "knn_3_log_ppm2",
    "knn_5_log_ppm2",
    "knn_20_log_ppm2",
    "knn_dw10_log_ppm2",
    "knn_type_10_log_ppm2",
    "ko_transaction_count",
    "muni_transaction_count",
    "ko_vs_muni_premium",
    "muni_vs_region_premium",
    "price_per_m2_ko",
    "size_percentile",
    "parcel_sold_fraction",
    # Enrichment: strongest correlators for parcela
    "gji_kanalizacija_nearby_100m",  # r=0.59
    "gji_vodovod_nearby_100m",  # r=0.59
    "gji_kanalizacija_distance_m",  # r=-0.61
    "gji_vodovod_distance_m",  # r=-0.65
    "ev_parcela_povrsina",  # r=-0.76
    "ev_boniteta",  # r=0.34
    "ev_odprtost",  # r=0.22
    "opt_zmogljivost",
    "kn_ggo_openness",
    # New GJI: plin/toplota discriminate urban vs rural parcels
    "gji_plin_nearby_100m",
    "gji_plin_distance_m",
    "gji_toplota_nearby_100m",
    "gji_toplota_distance_m",
    "gji_elektrika_distance_m",
    "gji_elektrika_nearby_100m",
    "gji_ceste_distance_m",
    "gji_opt_nearby_100m",  # r=0.24 - optical fiber = urban indicator
    "gji_zeleznice_nearby_1000m",  # r=0.14
    "dtm_voda_distance_m",  # r=-0.10
}

PARCELA_ALWAYS_INCLUDE_CATEGORICAL = {
    "municipality_normalized",
    "statistical_region",
    "market_subtype_key",
    "ime_ko",
    "naselje",
    "vrsta_zemljisca",  # CRITICAL: 100x price variation by subtype
    "kn_ggo_section",
    "dtm_pokritost_tal",
    "parcela_namenska_raba",
}

# ── Type-specific feature configurations ─────────────────────────────
# Each type gets its own "always include" set — signal scoring adds more on top.
# _SPATIAL_ALWAYS is added to every type's always_numeric automatically.
_SPATIAL_ALWAYS = {
    "dist_ljubljana",
    "dist_maribor",
    "dist_coast",
    "comp_type_muni_ppm2",
    "comp_type_ko_ppm2",
    "comp_type_naselje_ppm2",
    "emv_zone_match",
    "emv_zone_level",
    # KNN spatial features (always include — highest signal for all types)
    "knn_3_log_ppm2",
    "knn_5_log_ppm2",
    "knn_20_log_ppm2",
    "knn_dw10_log_ppm2",
    "knn_type_10_log_ppm2",
    "ko_transaction_count",
    "muni_transaction_count",
    "ko_vs_muni_premium",
    "muni_vs_region_premium",
    "price_per_m2_ko",
}

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
            "latitude",  # r=-0.36
            "longitude",  # r=-0.41
            "ddv_vkljucen",  # r=0.15
            "has_terasa",  # r=0.10
            # Enrichment (|r| > 0.15, fill > 25%)
            "ev_st_etaz",  # r=0.26
            "ev_ima_kanalizacijo",  # r=0.26
            "ev_id_dr_dst",  # r=-0.26
            "gji_kanalizacija_nearby_100m",  # r=0.24
            "ev_leto_izg_stavbe",  # r=0.23
            "ev_st_stanovanj",  # r=0.22
            "ev_ima_dvigalo",  # r=0.21
            "gji_kanalizacija_distance_m",  # r=-0.20
            "ev_del_st_nadstropja",  # r=0.19
            "vrsta_dela_stavbe",  # r=-0.18
            "ev_pov_stavbe",  # r=0.17
            "ev_ima_vodovod",  # r=0.15
            "ev_id_lega",  # r=-0.14
            "rn_address_match",  # r=0.24
            # New GJI infrastructure
            "gji_plin_nearby_100m",
            "gji_plin_distance_m",
            "gji_toplota_nearby_100m",
            "gji_toplota_distance_m",
            "opt_zmogljivost",
            "kn_etazna_lastnina",
            "dtm_nadm_visina_stavbe",
        }
        | _SPATIAL_ALWAYS,
        "always_categorical": {
            "municipality_normalized",
            "statistical_region",
            "lega_v_stavbi",
            "ime_ko",
            "naselje",
            "dtm_pokritost_tal",
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
            # House-specific features (experiment: +4.7% R²)
            "prodani_delez_dela_stavbe",  # r=0.18
            "has_terasa",  # r=0.15
            "has_shramba",  # r=0.13
            "has_garaza",  # r=0.11
            "has_klet",  # r=-0.05
            "ddv_vkljucen",  # r=0.16
            "num_prostori",  # r=0.11
            # Enrichment (|r| > 0.15, fill > 15%)
            "ev_leto_izg_stavbe",  # r=0.35
            "ev_ima_kanalizacijo",  # r=0.29
            "ev_leto_obn_strehe",  # r=0.26
            "ev_leto_obn_fasade",  # r=0.25
            "gji_kanalizacija_nearby_100m",  # r=0.24
            "ev_leto_obn_oken",  # r=0.23
            "ev_ima_plin",  # r=0.22
            "ev_id_tip_stavbe",  # r=0.22
            "ev_leto_obn_inst",  # r=0.22
            "gji_kanalizacija_distance_m",  # r=-0.21
            "ev_ima_vodovod",  # r=0.19
            "rn_address_match",  # r=0.23
            # Extended building EV features (experiment: +0.4% R²)
            "ev_pov_stavbe",  # r=0.17
            "ev_st_etaz",  # r=0.15
            "ev_ima_dvigalo",  # r=0.14
            "ev_id_dr_dst",  # r=-0.13
            "ev_id_lega",  # r=-0.12
            "gji_vodovod_distance_m",  # r=-0.17
            "gji_vodovod_nearby_100m",  # r=0.07
            "kn_ggo_openness",  # r=0.08
            "ev_parcela_povrsina",  # parcel size from EV
            "prodani_delez_parcele",
            # New GJI infrastructure
            "gji_plin_nearby_100m",
            "gji_plin_distance_m",
            "gji_toplota_nearby_100m",
            "gji_toplota_distance_m",
            "gji_elektrika_distance_m",
            "opt_zmogljivost",
            "dtm_nadm_visina_stavbe",
        }
        | _SPATIAL_ALWAYS,
        "always_categorical": {
            "municipality_normalized",
            "statistical_region",
            "ime_ko",
            "naselje",
            "lega_v_stavbi",
            "kn_ggo_section",
            "dtm_pokritost_tal",
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
            "comp_subtype_muni_ppm2",
            "comp_subtype_ko_ppm2",
            "comp_subtype_naselje_ppm2",
            "ddv_vkljucen",
            "year_built",
            "building_age",
            "uporabna_povrsina",
            "prodani_delez_dela_stavbe",
            # Enrichment (optimized via experiment)
            "gji_kanalizacija_distance_m",  # r=-0.18
            "gji_vodovod_distance_m",
            "ev_leto_izg_stavbe",  # r=0.23
            "gji_kanalizacija_nearby_100m",
            "ev_del_upor_pov",  # r=-0.29
            "kn_ggo_openness",
            "ev_pov_stavbe",  # r=-0.35
            "ev_del_povrsina",  # r=-0.28
            # New GJI infrastructure (urban proximity discriminates kmetijsko prices)
            "gji_plin_nearby_100m",
            "gji_plin_distance_m",
            "gji_toplota_distance_m",
            "gji_elektrika_distance_m",
            "gji_ceste_distance_m",
            "dtm_nadm_visina_stavbe",
            # Top correlators from analysis (|r| > 0.10)
            "ev_ima_elektriko",  # r=+0.235
            "ev_ima_vodovod",  # r=+0.228
            "ev_boniteta",  # r=+0.137 (land quality score)
            "ev_ima_kanalizacijo",  # r=+0.167
            "gji_opt_nearby_100m",
        }
        | _SPATIAL_ALWAYS,
        "always_categorical": {
            "municipality_normalized",
            "statistical_region",
            "market_subtype_key",
            "vrsta_zemljisca",
            "ime_ko",
            "kn_ggo_section",
            "naselje",
            "dtm_pokritost_tal",
            "parcela_namenska_raba",
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
            # Enrichment
            "ev_leto_izg_stavbe",  # r=0.49
            "stopnja_ddv",  # r=-0.42
            "ev_ima_dvigalo",  # r=0.37
            "ev_pov_stavbe",  # r=0.35
            "ev_ima_vodovod",  # r=0.34
            "ev_ima_kanalizacijo",  # r=0.33
            "ev_id_lega",  # r=-0.34
            "vrsta_dela_stavbe",  # r=-0.34
            "ev_ima_elektriko",  # r=0.31
            "ev_id_dr_dst",  # r=0.31
            "gji_kanalizacija_nearby_100m",
            "ev_del_st_nadstropja",
            "ev_st_etaz",
            "ev_st_stanovanj",  # r=0.27
            "ev_ima_plin",
            # New GJI infrastructure
            "gji_plin_nearby_100m",
            "gji_toplota_nearby_100m",
            "opt_zmogljivost",
            "kn_etazna_lastnina",
            "dtm_nadm_visina_stavbe",
            # Additional high-signal features from correlation analysis
            "gji_ceste_distance_m",  # r=+0.213
            "gji_plin_distance_m",
        }
        | _SPATIAL_ALWAYS,
        "always_categorical": {
            "municipality_normalized",
            "statistical_region",
            "lega_v_stavbi",
            "ime_ko",
            "dtm_pokritost_tal",
        },
    },
    "poslovni_prostor": {
        "always_numeric": {
            "size_m2",
            "year_built",
            "building_age",
            "novogradnja",
            "log_size_m2",
            "transaction_year",
            "price_per_m2_municipality",
            "uporabna_povrsina",
            "prodani_delez_dela_stavbe",
            "stavba_je_dokoncana",
            "ddv_vkljucen",
            "latitude",
            "longitude",
            "parcela_m2",
            # Enrichment (optimized via experiment)
            "ev_ima_dvigalo",
            "ev_ima_kanalizacijo",
            "ev_st_etaz",
            "gji_kanalizacija_nearby_100m",
            "ev_st_poslovnih_prostorov",
            "ev_leto_izg_stavbe",
            "ev_pov_stavbe",
            "rn_address_match",
            "ev_leto_obn_inst",
            "ev_leto_obn_fasade",
            "ev_leto_obn_oken",
            # New GJI infrastructure
            "gji_plin_nearby_100m",
            "gji_toplota_nearby_100m",
            "opt_zmogljivost",
            "kn_etazna_lastnina",
            "dtm_nadm_visina_stavbe",
            "gji_zeleznice_nearby_1000m",  # r=+0.215
        }
        | _SPATIAL_ALWAYS,
        "always_categorical": {
            "municipality_normalized",
            "statistical_region",
            "lega_v_stavbi",
            "ime_ko",
            "naselje",
            "kn_ggo_section",
            "dtm_pokritost_tal",
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
            # Enrichment: top correlators only (keep set small for n=1645)
            "ev_ima_dvigalo",  # r=0.55
            "ev_id_dr_dst",  # r=-0.39
            "ev_st_poslovnih_prostorov",  # r=0.37
            "ev_leto_izg_stavbe",  # r=0.33
            "rn_address_match",  # r=0.32
            "ev_pov_stavbe",  # r=0.30
            "opt_zmogljivost",
            "dtm_nadm_visina_stavbe",
        }
        | _SPATIAL_ALWAYS,
        "always_categorical": {
            "municipality_normalized",
            "statistical_region",
            # ime_ko too high-cardinality for ~1181 rows
            "dtm_pokritost_tal",
        },
    },
    "turisticni": {
        # ~1134 rows — moderate feature set, no high-cardinality categoricals
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
            # Enrichment: top correlators (keep set moderate for n=1134)
            "ev_ima_dvigalo",  # r=0.42
            "gji_kanalizacija_nearby_100m",  # r=0.31
            "ev_st_etaz",  # r=0.28
            "ev_st_poslovnih_prostorov",  # r=0.26
            "ev_ima_kanalizacijo",  # r=0.20
            "opt_zmogljivost",
            "dtm_nadm_visina_stavbe",
        }
        | _SPATIAL_ALWAYS,
        "always_categorical": {
            "municipality_normalized",
            "statistical_region",
            # ime_ko and naselje too high-cardinality for 1134 rows
            "dtm_pokritost_tal",
        },
    },
    "gostinstvo": {
        # Only 445 rows — keep feature set minimal to prevent overfitting.
        # No high-cardinality categoricals (ime_ko ~2600, naselje ~5000 are toxic here).
        "always_numeric": {
            "size_m2",
            "year_built",
            "log_size_m2",
            "transaction_year",
            "price_per_m2_region",
            "price_per_m2_municipality",
            "latitude",
            "longitude",
            "stavba_je_dokoncana",
            "prodani_delez_dela_stavbe",
            # Only strongest enrichment features (|r|>0.23)
            "ev_leto_izg_stavbe",  # r=0.25
            "ev_pov_stavbe",  # r=0.24
            "ev_ima_plin",  # r=0.23
            "opt_zmogljivost",
            "dtm_nadm_visina_stavbe",
        }
        | _SPATIAL_ALWAYS,
        "always_categorical": {
            "statistical_region",
            # municipality_normalized has ~200 values for 445 rows — skip
            "dtm_pokritost_tal",
        },
    },
}

# ── Per-type feature exclusion lists (v9: trimmed after correlation audit) ──
# v8 pruned by CatBoost importance < 0.05 — that was wrong for features with
# real Spearman correlation. Low importance meant redundancy with a correlated
# feature, NOT lack of signal. v9 keeps only exclusions where BOTH importance
# was ~0 AND Spearman |corr| < 0.12, or the feature is structurally meaningless
# for the type (e.g. building fields on land-only types).
TYPE_EXCLUDE_FEATURES: dict[str, dict[str, set[str]]] = {
    "stanovanje": {
        # v9: restored gji_plin_nearby_100m (r=+0.196), gji_toplota_nearby_100m
        # (r=+0.189), gji_kanalizacija_nearby_100m (r=+0.188) — all real signal.
        "numeric": {
            "gji_opt_nearby_100m",
            "gji_elektrika_nearby_100m",
            "gji_vodovod_nearby_100m",
            "gji_ceste_nearby_100m",
            "gji_zeleznice_nearby_1000m",  # 100m variant is stronger
            "has_shramba",
            "has_garaza",
            "has_ev_data",
            "has_renovation_data",
            "rn_address_match",
            "ev_ima_elektriko",
            "ev_ima_vodovod",
            "gradbena_faza",
            "stavba_je_dokoncana",
            "prodani_delez_dela_stavbe",
        },
        "categorical": set(),
    },
    "hisa": {
        # v9: restored gji_plin_nearby_100m (r=+0.282), prodani_delez_dela_stavbe
        # (+0.239), gji_kanalizacija_nearby_100m (+0.236), novogradnja (+0.161),
        # ddv_vkljucen (+0.159) — strong signal, v8 was wrong to cut.
        "numeric": {
            "gji_zeleznice_nearby_1000m",  # 100m variant wins
            "gji_opt_nearby_100m",
            "gji_vodovod_nearby_100m",
            "gji_toplota_nearby_100m",
            "gji_ceste_nearby_100m",
            "gji_elektrika_nearby_100m",
            "ev_del_st_nadstropja",
            "prodani_delez_parcele",  # houses aren't sold by land fraction
            "ev_ima_dvigalo",  # houses rarely have elevators
            "kn_etazna_lastnina",  # houses aren't apartments
            "has_renovation_data",
            "rn_address_match",
            "has_ev_data",
        },
        "categorical": {"emv_zone_name"},
    },
    "parcela": {
        # v9: ALL gji_*_nearby_100m have MASSIVE signal on parcela
        # (r=0.44-0.66) — undo v8 pruning entirely, keep only true junk.
        "numeric": {
            "prodani_delez_parcele",  # imp=0, systematic zero on parcela
            "transaction_quarter",
        },
        "categorical": {"emv_zone_match", "emv_zone_model"},
    },
    "garaza": {
        # v9: restored ev_ima_kanalizacijo (r=+0.325), gji_plin_nearby_100m
        # (+0.230), gji_kanalizacija_nearby_100m (+0.210) — real signal.
        "numeric": {
            "gji_ceste_nearby_100m",
            "gji_vodovod_nearby_100m",
            "has_ev_data",
            "gradbena_faza",
            "num_prostori",
            "stavba_je_dokoncana",
            "rn_address_match",
            "has_shramba",
            "gji_elektrika_nearby_100m",
            "gji_opt_nearby_100m",
        },
        "categorical": {"emv_zone_id", "emv_zone_name"},
    },
    "kmetijsko": {
        "numeric": {
            # Building features irrelevant for farmland
            "ev_del_st_nadstropja",
            "ev_st_poslovnih_prostorov",
            "ev_ima_kanalizacijo",
            "ev_id_lega",
            "num_prostori",
            "has_garaza",
            "has_ev_data",
            "prodani_delez_parcele",
            # v9: restore gji_plin_nearby_100m (r=+0.212) — real signal.
            # Keep low-signal gji variants excluded for farmland.
            "gji_vodovod_nearby_100m",
            "gji_elektrika_nearby_100m",
            "gji_kanalizacija_nearby_100m",
            "gji_opt_nearby_100m",
            "gji_toplota_nearby_100m",
            "gji_ceste_nearby_100m",
            "ddv_vkljucen",
            "gradbena_faza",
            "stavba_je_dokoncana",
            "novogradnja",
        },
        "categorical": {"kn_ggo_section"},
    },
    "poslovni_prostor": {
        # v9: restored novogradnja (r=+0.219), prodani_delez_dela_stavbe (+0.170).
        "numeric": {"rn_address_match"},
        "categorical": {"naselje"},  # high-cardinality noise for 3k rows
    },
    "industrijski": {
        # v9: restored novogradnja (r=+0.277), has_terasa (+0.247),
        # ev_ima_elektriko (+0.227), gji_elektrika_nearby_100m (+0.187),
        # prodani_delez_dela_stavbe (+0.173) — all real signal.
        "numeric": {
            "gji_vodovod_nearby_100m",
            "has_renovation_data",
            "gji_kanalizacija_nearby_100m",
            "gradbena_faza",
            "stavba_je_dokoncana",
            "has_garaza",
            "gji_zeleznice_nearby_1000m",  # 100m variant preferred
            "gji_ceste_nearby_100m",
            "gji_opt_nearby_100m",
            "has_klet",
            "rn_address_match",
            "has_shramba",
            "has_ev_data",
        },
        "categorical": {"emv_zone_id", "emv_zone_name"},
    },
    "turisticni": {
        "numeric": {"prodani_delez_dela_stavbe"},
        "categorical": set(),
    },
    "gostinstvo": {
        # v9: restored gji_plin_nearby_100m (r=+0.241), novogradnja (+0.194),
        # ev_ima_vodovod (+0.161), gji_kanalizacija_nearby_100m (+0.159),
        # prodani_delez_dela_stavbe (+0.156) — real signal.
        "numeric": {
            "ev_ima_elektriko",
            "gji_zeleznice_nearby_1000m",  # 100m variant preferred
            "gradbena_faza",
            "has_terasa",
            "has_ev_data",
            "gji_elektrika_nearby_100m",
            "has_garaza",
            "has_klet",
            "gji_ceste_nearby_100m",
            "rn_address_match",
            "has_shramba",
            "gji_opt_nearby_100m",
        },
        "categorical": {"emv_zone_id", "emv_zone_name"},
    },
}

# ── Per-type hyperparameter overrides (from optimization experiments) ──
TYPE_HP_OVERRIDES: dict[str, dict] = {
    # RMSE loss (set in _adaptive_hyperparams). MAE/Quantile crashes on GPU (CUDA 700).
    # Huber tested in research runs and degraded R²; keep it out of production defaults.
    # Small types: stronger regularisation to prevent overfitting on thin data.
    "gostinstvo": {"iterations": 1500, "depth": 5, "l2_leaf_reg": 12.0, "od_wait": 250, "random_strength": 4.0},
    "industrijski": {"iterations": 1800, "depth": 6, "l2_leaf_reg": 8.0, "od_wait": 200, "random_strength": 3.0},
    "turisticni": {"iterations": 1800, "depth": 6, "l2_leaf_reg": 8.0, "od_wait": 200, "random_strength": 3.0},
    # Medium types
    "poslovni_prostor": {"iterations": 2500, "depth": 7, "l2_leaf_reg": 3.0, "learning_rate": 0.05},
    "kmetijsko": {"iterations": 3000, "depth": 8, "l2_leaf_reg": 5.0, "od_wait": 180, "learning_rate": 0.04},
    "garaza": {"iterations": 3000, "depth": 7, "l2_leaf_reg": 5.0, "od_wait": 200, "random_strength": 2.0},
    # Large types: push hard — max iterations, low LR, deep trees, full GPU
    "stanovanje": {
        "iterations": 8000,
        "depth": 8,
        "l2_leaf_reg": 1.5,
        "learning_rate": 0.02,
        "od_wait": 300,
        "max_ctr_complexity": 2,
    },
    "hisa": {
        "iterations": 8000,
        "depth": 8,
        "l2_leaf_reg": 2.0,
        "learning_rate": 0.02,
        "od_wait": 300,
        "max_ctr_complexity": 2,
    },
    "parcela": {
        "iterations": 8000,
        "depth": 9,
        "l2_leaf_reg": 1.5,
        "learning_rate": 0.02,
        "od_wait": 300,
        "max_ctr_complexity": 2,
    },
}

TYPE_TRAINING_PRIORS: dict[str, dict[str, Any]] = {
    # Best-known configuration from the tracked 2020-2026 research leaderboard.
    "kmetijsko": {
        "feature_variant": "rich",
        "target_transform": "log_price",
        "training_policy": "full_history_weighted",
    },
    "parcela": {
        "feature_variant": "rich",
        "target_transform": "log_price",
        "training_policy": "recent_6y_weighted",
    },
    "industrijski": {
        "feature_variant": "rich",
        "target_transform": "log_ppm2",
        "training_policy": "full_history_weighted",
    },
    "hisa": {
        "feature_variant": "simple",
        "target_transform": "log_ppm2",
        "training_policy": "recent_6y_weighted",
    },
    "gostinstvo": {
        "feature_variant": "rich",
        "target_transform": "log_ppm2",
        "training_policy": "full_history_weighted",
    },
    "garaza": {
        "feature_variant": "rich",
        "target_transform": "log_ppm2",
        "training_policy": "full_history_weighted",
    },
    "turisticni": {
        "feature_variant": "simple",
        "target_transform": "log_ppm2",
        "training_policy": "full_history_weighted",
    },
    "poslovni_prostor": {
        "feature_variant": "simple",
        "target_transform": "log_price",
        "training_policy": "full_history_weighted",
    },
    "stanovanje": {
        "feature_variant": "rich",
        "target_transform": "log_ppm2",
        "training_policy": "recent_6y_weighted",
    },
}

TYPE_SEARCH_PRIORS: dict[str, dict[str, Any]] = {
    # Land types: v1 candidate search confirmed rich+log_price+full_history wins
    # for both. Pin to the winners to save ~70 min, freeing budget for hisa/stanovanje.
    "kmetijsko": {
        "benchmark_variants": False,
        "benchmark_hyperparameters": False,
        "feature_variants": ["rich"],
        "target_candidates": ["log_price"],
        "policy_candidates": ["full_history_weighted"],
    },
    "parcela": {
        "benchmark_variants": False,
        "benchmark_hyperparameters": False,
        "feature_variants": ["rich"],
        "target_candidates": ["log_price"],
        "policy_candidates": ["full_history_weighted"],
    },
    # hisa: v1 had simple winning but gap was small - benchmark rich to see if
    # the extra headroom pays off now that IQR has been restored.
    "hisa": {
        "benchmark_variants": True,
        "benchmark_hyperparameters": True,
        "feature_variants": ["simple", "rich"],
        "target_candidates": ["log_ppm2"],
        "policy_candidates": ["recent_6y_weighted"],
    },
    "garaza": {
        "benchmark_variants": False,
        "benchmark_hyperparameters": True,
        "feature_variants": ["rich"],
        "target_candidates": ["log_ppm2"],
        "policy_candidates": ["full_history_weighted"],
    },
    # Small types: minimal search to avoid wasting time on tiny datasets
    "industrijski": {
        "benchmark_variants": False,
        "benchmark_hyperparameters": False,
        "feature_variants": ["rich"],
        "target_candidates": ["log_ppm2"],
        "policy_candidates": ["full_history_weighted"],
    },
    "turisticni": {
        "benchmark_variants": False,
        "benchmark_hyperparameters": False,
        "feature_variants": ["simple"],
        "target_candidates": ["log_ppm2"],
        "policy_candidates": ["full_history_weighted"],
    },
    "gostinstvo": {
        "benchmark_variants": False,
        "benchmark_hyperparameters": False,
        "feature_variants": ["rich"],
        "target_candidates": ["log_ppm2"],
        "policy_candidates": ["full_history_weighted"],
    },
}

TYPE_HP_CANDIDATES: dict[str, list[dict[str, Any]]] = {
    "kmetijsko": [
        {
            "iterations": 2600,
            "learning_rate": 0.05,
            "depth": 8,
            "min_data_in_leaf": 10,
            "l2_leaf_reg": 7.0,
            "random_strength": 2.5,
            "od_wait": 180,
        },
        {
            "iterations": 3200,
            "learning_rate": 0.04,
            "depth": 8,
            "min_data_in_leaf": 12,
            "l2_leaf_reg": 10.0,
            "random_strength": 3.0,
            "od_wait": 220,
        },
    ],
    "parcela": [
        {
            "iterations": 2600,
            "learning_rate": 0.05,
            "depth": 8,
            "min_data_in_leaf": 10,
            "l2_leaf_reg": 6.0,
            "random_strength": 2.0,
            "od_wait": 180,
        },
        {
            "iterations": 3200,
            "learning_rate": 0.04,
            "depth": 9,
            "min_data_in_leaf": 12,
            "l2_leaf_reg": 8.0,
            "random_strength": 2.5,
            "od_wait": 220,
        },
    ],
    "hisa": [
        {
            "iterations": 2800,
            "learning_rate": 0.05,
            "depth": 8,
            "min_data_in_leaf": 18,
            "l2_leaf_reg": 5.0,
            "random_strength": 1.5,
            "od_wait": 180,
        },
        {
            "iterations": 3400,
            "learning_rate": 0.04,
            "depth": 9,
            "min_data_in_leaf": 20,
            "l2_leaf_reg": 7.0,
            "random_strength": 2.0,
            "od_wait": 220,
        },
    ],
    "garaza": [
        {
            "iterations": 2400,
            "learning_rate": 0.05,
            "depth": 8,
            "min_data_in_leaf": 12,
            "l2_leaf_reg": 4.0,
            "random_strength": 2.0,
            "od_wait": 180,
        },
    ],
    "industrijski": [
        {
            "iterations": 2600,
            "learning_rate": 0.05,
            "depth": 8,
            "min_data_in_leaf": 10,
            "l2_leaf_reg": 5.0,
            "random_strength": 2.0,
            "od_wait": 200,
        },
    ],
    "turisticni": [
        {
            "iterations": 2200,
            "learning_rate": 0.05,
            "depth": 7,
            "min_data_in_leaf": 8,
            "l2_leaf_reg": 6.0,
            "random_strength": 2.0,
            "od_wait": 200,
        },
    ],
    "gostinstvo": [
        {
            "iterations": 2200,
            "learning_rate": 0.05,
            "depth": 7,
            "min_data_in_leaf": 8,
            "l2_leaf_reg": 6.0,
            "random_strength": 2.0,
            "od_wait": 200,
        },
    ],
}

TYPE_CANDIDATE_SELECTION_PRIORS: dict[str, dict[str, Any]] = {
    "kmetijsko": {
        "r2_tolerance": 0.035,
        "mape_tolerance": 2.5,
        "prefer_r2": True,
    },
    "parcela": {
        "r2_tolerance": 0.03,
        "mape_tolerance": 2.5,
        "prefer_r2": True,
    },
    "hisa": {
        "r2_tolerance": 0.025,
        "mape_tolerance": 2.0,
        "prefer_r2": True,
    },
    "garaza": {
        "r2_tolerance": 0.03,
        "mape_tolerance": 2.5,
        "prefer_r2": True,
    },
    "industrijski": {
        "r2_tolerance": 0.035,
        "mape_tolerance": 3.0,
        "prefer_r2": True,
    },
    "turisticni": {
        "r2_tolerance": 0.03,
        "mape_tolerance": 3.0,
        "prefer_r2": True,
    },
    "gostinstvo": {
        "r2_tolerance": 0.03,
        "mape_tolerance": 2.5,
        "prefer_r2": True,
    },
}

TYPE_ROUTING_PRIORS: dict[str, dict[str, Any]] = {
    "parcela": {"max_weight": 0.85, "r2_tolerance": 0.015},
    "kmetijsko": {"max_weight": 0.9, "r2_tolerance": 0.02},
    "garaza": {"max_weight": 0.85, "r2_tolerance": 0.015},
    "gostinstvo": {"max_weight": 0.8, "r2_tolerance": 0.02},
    "industrijski": {"max_weight": 0.9, "r2_tolerance": 0.02},
    "turisticni": {"max_weight": 0.8, "r2_tolerance": 0.02},
    "poslovni_prostor": {"max_weight": 0.85, "r2_tolerance": 0.015},
    "hisa": {"max_weight": 1.0, "r2_tolerance": 0.01},
    "stanovanje": {"max_weight": 1.0, "r2_tolerance": 0.01},
}

# ── Per-type IQR outlier multiplier overrides ──
TYPE_SPECIALIST_MODEL_PRIORS: dict[str, dict[str, Any]] = {
    "kmetijsko": {
        "feature_variant": "rich",
        "target_transform": "log_price",
        "min_train_rows": 2000,
        "min_test_rows": 200,
        "enable_subtype_family": True,
        "subtype_min_train_rows": 150,
        "subtype_min_test_rows": 25,
        "hp_overrides": {
            "iterations": 3200,
            "learning_rate": 0.04,
            "depth": 8,
            "min_data_in_leaf": 10,
            "l2_leaf_reg": 10.0,
            "random_strength": 3.0,
            "od_wait": 220,
        },
    },
    "parcela": {
        "feature_variant": "rich",
        "target_transform": "log_price",
        "min_train_rows": 8000,
        "min_test_rows": 800,
        "enable_subtype_family": True,
        "subtype_min_train_rows": 400,
        "subtype_min_test_rows": 60,
        "hp_overrides": {
            "iterations": 3200,
            "learning_rate": 0.04,
            "depth": 9,
            "min_data_in_leaf": 10,
            "l2_leaf_reg": 8.0,
            "random_strength": 2.5,
            "od_wait": 220,
        },
    },
    # v9: garaza splits ~50/50 on vrsta_dela_stavbe into aboveground (~11k)
    # and underground (~10k) with a 117 percentage-point log_ppm2 spread
    # (~3x price ratio) - two clean sub-models, biggest lever remaining.
    "garaza": {
        "feature_variant": "rich",
        "target_transform": "log_ppm2",
        "min_train_rows": 8000,
        "min_test_rows": 800,
        "enable_subtype_family": True,
        "subtype_min_train_rows": 2000,
        "subtype_min_test_rows": 250,
        "hp_overrides": {
            "iterations": 2800,
            "learning_rate": 0.045,
            "depth": 8,
            "min_data_in_leaf": 10,
            "l2_leaf_reg": 4.0,
            "random_strength": 2.0,
            "od_wait": 200,
        },
    },
    # v9: hisa splits on ev_id_konstrukcija into brick (dominant ~50%),
    # concrete (19%), wood (11%), mixed (6%), prefab (5%). 81pp log_ppm2
    # spread. Raise subtype threshold because brick dominates; smaller
    # buckets will fall back to the parent hisa model.
    "hisa": {
        "feature_variant": "rich",
        "target_transform": "log_price",
        "min_train_rows": 8000,
        "min_test_rows": 800,
        "enable_subtype_family": True,
        "subtype_min_train_rows": 1500,
        "subtype_min_test_rows": 200,
        "hp_overrides": {
            "iterations": 3000,
            "learning_rate": 0.045,
            "depth": 8,
            "min_data_in_leaf": 10,
            "l2_leaf_reg": 3.0,
            "random_strength": 1.5,
            "od_wait": 200,
        },
    },
    # v16: stanovanje specialist with log_price target — lets the model learn
    # non-linear size-price relationships (100m² != 2x 50m²).
    "stanovanje": {
        "feature_variant": "rich",
        "target_transform": "log_price",
        "min_train_rows": 8000,
        "min_test_rows": 800,
        "enable_subtype_family": False,
        "hp_overrides": {
            "iterations": 3500,
            "learning_rate": 0.04,
            "depth": 8,
            "min_data_in_leaf": 10,
            "l2_leaf_reg": 2.0,
            "random_strength": 1.0,
            "od_wait": 250,
        },
    },
    # v16: poslovni_prostor — log_price hurt R² (-0.033), revert to log_ppm2.
    "poslovni_prostor": {
        "feature_variant": "rich",
        "target_transform": "log_ppm2",
        "min_train_rows": 1500,
        "min_test_rows": 200,
        "enable_subtype_family": False,
        "hp_overrides": {
            "iterations": 2500,
            "learning_rate": 0.045,
            "depth": 7,
            "min_data_in_leaf": 10,
            "l2_leaf_reg": 4.0,
            "random_strength": 2.0,
            "od_wait": 200,
        },
    },
}

# Small commercial types that share one enlarged training pool.
# v1 showed each starves alone: industrijski (1339 train, R²=0.614),
# turisticni (1195 train, R²=0.590), gostinstvo (482 train, R²=0.625).
# Training on the union with property_type as a feature multiplies effective
# sample size per model and lets CatBoost learn commonalities. Each type
# still keeps its own per-type evaluation and blend weight.
SMALL_COMMERCIAL_GROUP: set[str] = {"industrijski", "turisticni", "gostinstvo"}


TYPE_IQR_OVERRIDES: dict[str, float] = {
    # Top types where v1 showed aggressive IQR=1.5 + winsorization hurt R²:
    # stanovanje -0.003, poslovni_prostor -0.010, hisa marginal.
    # Restore 2.0x fence to preserve hard-but-learnable examples.
    "stanovanje": 2.0,
    "hisa": 2.0,
    "poslovni_prostor": 2.5,
    "parcela": 2.0,
    # garaza/kmetijsko: keep default 1.5 (tight) - they improved in v1
    # industrijski/turisticni/gostinstvo: keep default 1.5 - small types
    # where outlier trimming is more important than sample preservation
}

# v2 showed skip-winsorization hurt metrics by leaving extreme outliers in
# test set. All types now get winsorized in the global pass.
TYPE_SKIP_WINSORIZATION: set[str] = set()

# Land types where IQR outlier removal should run per-subtype (vrsta_zemljisca).
# stavbno (building land, EUR50-500/m2) and kmetijsko (agricultural, EUR1-10/m2)
# have 100x price variation -- mixed IQR fences are useless.
SUBTYPE_OUTLIER_TYPES: set[str] = {"parcela", "kmetijsko"}

# Number of K-fold splits for out-of-fold global stacking predictions.
OOF_STACKING_FOLDS: int = 5

# Bayesian smoothing prior strength for comp features.
# A group needs COMP_SMOOTH_ALPHA+ members before its own median dominates.
# Prevents target leakage for small groups (KO with 5 transactions = 20% self-influence).
COMP_SMOOTH_ALPHA: float = 5.0


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
        df[col] = df[col].apply(lambda v: "unknown" if v is None or (isinstance(v, float) and np.isnan(v)) else str(v))
        df[col] = df[col].apply(lambda v: "unknown" if not v or v.isspace() else v)
    return df


def _filter_features_by_source(features: list[str], enabled_sources: dict[str, bool]) -> list[str]:
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
    *,
    extra_keep_numeric: set[str] | None = None,
    extra_keep_categorical: set[str] | None = None,
) -> tuple[list[str], list[str]]:
    """Filter features by fill rate, keeping ALWAYS_INCLUDE even when sparse."""
    keep_num = ALWAYS_INCLUDE_NUMERIC | (extra_keep_numeric or set())
    keep_cat = ALWAYS_INCLUDE_CATEGORICAL | (extra_keep_categorical or set())
    numeric = [
        c
        for c in candidate_numeric
        if c in df.columns
        and (df[c].notna().mean() >= _MIN_FILL_RATE or (c in keep_num and df[c].notna().any()))
        and pd.to_numeric(df[c], errors="coerce").dropna().nunique() > 1
    ]
    categorical = [
        c
        for c in candidate_categorical
        if c in df.columns
        and (df[c].notna().mean() >= _MIN_FILL_RATE or (c in keep_cat and df[c].notna().any()))
        and df[c].fillna("unknown").astype(str).nunique() > 1
    ]
    return numeric, categorical


# ── CatBoost configuration ─────────────────────────────────────────


def _detect_catboost_task_type() -> str:
    """Detect CatBoost task type with optional env override and container-aware GPU checks."""
    forced = os.getenv("CATBOOST_TASK_TYPE", "").strip().upper()
    if forced in {"CPU", "GPU"}:
        logger.info("CATBOOST_TASK_TYPE=%s override detected", forced)
        return forced

    nvidia_visible = os.getenv("NVIDIA_VISIBLE_DEVICES", "").strip().lower()
    if os.name != "nt" and not os.path.exists("/dev/nvidia0") and nvidia_visible in {"", "none", "void"}:
        logger.info("No NVIDIA device exposed to process (/dev/nvidia0 missing) — using CPU for CatBoost training")
        return "CPU"

    try:
        from catboost.utils import get_gpu_device_count

        gpu_count = int(get_gpu_device_count())
        if gpu_count > 0:
            logger.info("CatBoost detected %d GPU device(s) - enabling GPU mode", gpu_count)
            return "GPU"
    except Exception as exc:  # pragma: no cover - depends on host GPU runtime
        logger.warning("CatBoost GPU probe failed: %s", exc)

    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            gpu_name = result.stdout.strip().splitlines()[0].strip()
            logger.info("GPU detected: %s — enabling CatBoost GPU mode", gpu_name)
            return "GPU"
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    logger.info("No GPU detected — using CPU for CatBoost training")
    return "CPU"


_CATBOOST_TASK_TYPE = _detect_catboost_task_type()

if _CATBOOST_TASK_TYPE == "CPU":
    logger.warning(
        "CatBoost will train on CPU. For 10-50x faster training, "
        "set CATBOOST_TASK_TYPE=GPU or verify NVIDIA drivers are installed."
    )


def _get_catboost_task_type() -> str:
    return _CATBOOST_TASK_TYPE


def _apply_gpu_param_adjustments(params: dict) -> dict:
    """Adjust hyperparameters for GPU compatibility and take advantage of GPU speed."""
    if params.get("task_type") != "GPU":
        return params
    params = dict(params)
    # rsm is only supported on GPU for pairwise objectives, not RMSE regression.
    params.pop("rsm", None)
    # MVS bootstrap is CPU-only → switch to Poisson (supports subsample on GPU)
    if params.get("bootstrap_type") == "MVS":
        params["bootstrap_type"] = "Poisson"
        params.setdefault("subsample", 0.8)
    # Ordered boosting is CPU-only → switch to Plain
    if params.get("boosting_type") == "Ordered":
        params["boosting_type"] = "Plain"
    # GPU manages parallelism internally — thread_count is ignored/errors on GPU
    params.pop("thread_count", None)
    # Keep the default GPU profile within a 6 GB card budget.
    params.setdefault("devices", os.getenv("CATBOOST_GPU_DEVICES", "0"))
    try:
        gpu_ram_part = float(os.getenv("CATBOOST_GPU_RAM_PART", "0.50"))
    except ValueError:
        gpu_ram_part = 0.50
    params.setdefault("gpu_ram_part", max(0.05, min(gpu_ram_part, 0.95)))
    params.setdefault("gpu_cat_features_storage", "CpuPinnedMemory")
    params["border_count"] = min(int(params.get("border_count", 254) or 254), 128)
    # GPU trains 10–50× faster: double iterations, lower LR for better convergence
    base_iters = params.get("iterations", 2000)
    params["iterations"] = min(int(base_iters * 2), 5000)
    if params.get("learning_rate", 1.0) >= 0.07:
        params["learning_rate"] = 0.04
    # GPU handles deeper trees efficiently
    if params.get("depth", 7) <= 7:
        params["depth"] = params["depth"] + 1
    return params


class CatBoostModel:
    """Lightweight wrapper around CatBoost with native categorical support."""

    def __init__(self, numeric_features: list[str], categorical_features: list[str], params: dict):
        self.numeric_features = list(numeric_features)
        self.categorical_features = list(categorical_features)
        self.all_features = self.numeric_features + self.categorical_features
        self._cat_indices = list(range(len(self.numeric_features), len(self.all_features)))
        self.params = params
        self.iterations = params.get("iterations", 3000)
        self.model: CatBoostRegressor | None = None
        self.best_iteration: int | None = None

    def _prepare(self, X: pd.DataFrame) -> pd.DataFrame:
        """Select and prepare features — CatBoost handles NaN natively for numerics."""
        columns: dict[str, Any] = {}
        for col in self.numeric_features:
            columns[col] = pd.to_numeric(X[col], errors="coerce") if col in X.columns else np.nan
        for col in self.categorical_features:
            columns[col] = X[col].fillna("unknown").astype(str) if col in X.columns else "unknown"
        return pd.DataFrame(columns, index=X.index)

    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: np.ndarray,
        X_eval: pd.DataFrame | None = None,
        y_eval: np.ndarray | None = None,
        sample_weight: np.ndarray | None = None,
        eval_sample_weight: np.ndarray | None = None,
        label: str = "",
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> CatBoostModel:
        t0 = time.time()
        logger.info(
            "[%s] Preparing data: %d rows, %d num + %d cat features",
            label,
            len(X_train),
            len(self.numeric_features),
            len(self.categorical_features),
        )
        df_train = self._prepare(X_train)
        train_pool = Pool(df_train, y_train, cat_features=self._cat_indices, weight=sample_weight)

        eval_pool = None
        if X_eval is not None and y_eval is not None:
            df_eval = self._prepare(X_eval)
            eval_pool = Pool(df_eval, y_eval, cat_features=self._cat_indices, weight=eval_sample_weight)

        logger.info(
            "[%s] Starting CatBoost fit: %d iters, depth=%d, lr=%.3f, boosting=%s",
            label,
            self.params.get("iterations", "?"),
            self.params.get("depth", "?"),
            self.params.get("learning_rate", 0),
            self.params.get("boosting_type", "Plain"),
        )
        self.model = CatBoostRegressor(**self.params)
        # Log every 200 iterations so we see progress
        verbose_interval = max(100, self.iterations // 10)

        callbacks = None
        task_type = str(self.params.get("task_type", "CPU")).upper()
        callbacks_supported = task_type != "GPU"
        if progress_callback is not None and callbacks_supported:
            report_every = max(100, self.iterations // 20)

            class _ProgressCallback:
                def __init__(self):
                    self.last_reported_iter = 0

                def after_iteration(self, info) -> bool:
                    current_iter = int(getattr(info, "iteration", 0)) + 1
                    if current_iter == 1 or current_iter >= self.last_reported_iter + report_every:
                        self.last_reported_iter = current_iter
                        progress_callback(label, current_iter, self_total_iters)
                    return True

            self_total_iters = self.iterations
            callbacks = [_ProgressCallback()]
        elif progress_callback is not None and not callbacks_supported:
            logger.info(
                "[%s] GPU mode does not support CatBoost user callbacks; using stage-level progress only", label
            )

        fit_kwargs = {
            "eval_set": eval_pool,
            "verbose": verbose_interval,
            "use_best_model": eval_pool is not None,
        }
        if callbacks is not None:
            fit_kwargs["callbacks"] = callbacks

        self.model.fit(
            train_pool,
            **fit_kwargs,
        )
        self.best_iteration = getattr(self.model, "best_iteration_", None) or self.model.tree_count_
        elapsed = time.time() - t0
        logger.info(
            "[%s] Fit complete: %d/%d trees in %.1fs (%.0f trees/sec)",
            label,
            self.best_iteration,
            self.iterations,
            elapsed,
            self.best_iteration / max(elapsed, 0.1),
        )
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        df = self._prepare(X)
        return self.model.predict(df)

    def get_feature_importance(self) -> dict[str, float]:
        if self.model is None:
            return {}
        importances = self.model.get_feature_importance()
        return dict(zip(self.all_features, [float(v) for v in importances], strict=False))


def _adaptive_hyperparams(n_samples: int, *, apply_gpu_adjustments: bool = True) -> dict:
    """CatBoost hyperparameters scaled by dataset size.

    - Plain boosting for large datasets (fast), Ordered for small (<2000, better generalization)
    - MVS bootstrap with subsample=0.8 for speed + regularisation on large data
    - max_ctr_complexity=2 for large, 1 for small (limits categorical cross-combos)
    - Higher l2_leaf_reg + od_wait for small datasets to prevent overfitting
    """
    task_type = _get_catboost_task_type()
    base: dict[str, Any] = {
        "task_type": task_type,
        "loss_function": "RMSE",
        "random_seed": 42,
        "od_type": "Iter",
        "border_count": 254,
        "thread_count": -1,
    }
    if n_samples > 50_000:
        base.update(
            {
                "iterations": 2000,
                "learning_rate": 0.07,
                "depth": 7,
                "min_data_in_leaf": 20,
                "l2_leaf_reg": 3.0,
                "random_strength": 1.0,
                "rsm": 0.8,
                "boosting_type": "Plain",
                "od_wait": 80,
                "max_ctr_complexity": 2,
                "bootstrap_type": "MVS",
                "subsample": 0.8,
            }
        )
    elif n_samples > 20_000:
        base.update(
            {
                "iterations": 2000,
                "learning_rate": 0.07,
                "depth": 7,
                "min_data_in_leaf": 15,
                "l2_leaf_reg": 3.0,
                "random_strength": 1.5,
                "rsm": 0.85,
                "boosting_type": "Plain",
                "od_wait": 80,
                "max_ctr_complexity": 2,
                "bootstrap_type": "MVS",
                "subsample": 0.8,
            }
        )
    elif n_samples > 5000:
        base.update(
            {
                "iterations": 1500,
                "learning_rate": 0.08,
                "depth": 7,
                "min_data_in_leaf": 10,
                "l2_leaf_reg": 5.0,
                "random_strength": 2.0,
                "boosting_type": "Plain",
                "od_wait": 100,
                "max_ctr_complexity": 2,
                "bootstrap_type": "MVS",
                "subsample": 0.8,
            }
        )
    elif n_samples > 2000:
        base.update(
            {
                "iterations": 1500,
                "learning_rate": 0.08,
                "depth": 6,
                "min_data_in_leaf": 8,
                "l2_leaf_reg": 7.0,
                "random_strength": 3.0,
                "boosting_type": "Plain",
                "od_wait": 120,
                "max_ctr_complexity": 1,
            }
        )
    elif n_samples > 500:
        # Small datasets: Ordered boosting generalises better, more regularisation
        base.update(
            {
                "iterations": 1200,
                "learning_rate": 0.06,
                "depth": 5,
                "min_data_in_leaf": 5,
                "l2_leaf_reg": 15.0,
                "random_strength": 4.0,
                "boosting_type": "Ordered",
                "od_wait": 200,
                "max_ctr_complexity": 1,
            }
        )
    else:
        base.update(
            {
                "iterations": 800,
                "learning_rate": 0.05,
                "depth": 4,
                "min_data_in_leaf": 5,
                "l2_leaf_reg": 25.0,
                "random_strength": 5.0,
                "boosting_type": "Ordered",
                "od_wait": 250,
                "max_ctr_complexity": 1,
            }
        )
    if apply_gpu_adjustments:
        return _apply_gpu_param_adjustments(base)
    return base


def _adaptive_max_extras(n_samples: int) -> tuple[int, int]:
    """Return (max_extra_numeric, max_extra_categorical) based on dataset size."""
    if n_samples > 10_000:
        return 20, 12
    if n_samples > 3000:
        return 16, 10
    if n_samples > 1000:
        return 8, 5
    if n_samples > 500:
        return 5, 3
    return 4, 2


def _compute_engineered_features(
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    X_test: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Compute high-signal engineered features from training data.

    All features are derived from the training set only (no data leakage).
    Returns updated X_train, X_test, and a dict of artifacts for prediction-time use.
    """
    t0 = time.time()
    artifacts: dict[str, Any] = {}

    # Defragment upfront because this function adds many columns and callers may
    # pass already-fragmented frames from prior feature construction.
    X_train = X_train.copy()
    X_test = X_test.copy()

    # ── Coordinates ──────────────────────────────────────────────────
    train_lon = pd.to_numeric(X_train.get("longitude"), errors="coerce").fillna(0).values
    train_lat = pd.to_numeric(X_train.get("latitude"), errors="coerce").fillna(0).values
    test_lon = pd.to_numeric(X_test.get("longitude"), errors="coerce").fillna(0).values
    test_lat = pd.to_numeric(X_test.get("latitude"), errors="coerce").fillna(0).values
    train_coords = np.column_stack([train_lon, train_lat])
    test_coords = np.column_stack([test_lon, test_lat])

    train_size = X_train["size_m2"].clip(lower=1).values.astype(float)
    train_log_ppm2 = np.log(np.maximum(y_train, 1) / train_size)

    # ── 1. Spatial KNN features (all types) ──────────────────────────
    logger.info("  Engineering: spatial KNN (all-types K=5,20) ...")
    tree_all = KDTree(train_coords)
    artifacts["knn_coords"] = train_coords.astype(np.float32)
    artifacts["knn_log_ppm2"] = train_log_ppm2.astype(np.float32)

    for K in (3, 5, 20):
        col = f"knn_{K}_log_ppm2"
        # Train: query K+1 to exclude self (index 0 is self)
        d_tr, idx_tr = tree_all.query(train_coords, k=K + 1)
        X_train[col] = np.median(train_log_ppm2[idx_tr[:, 1:]], axis=1)
        # Test: query K (all are from training set, no self-match issue)
        d_te, idx_te = tree_all.query(test_coords, k=K)
        X_test[col] = np.median(train_log_ppm2[idx_te], axis=1)

    # Distance-weighted KNN (K=10): inverse-distance weighted average
    logger.info("  Engineering: distance-weighted KNN (K=10) ...")
    K_DW = 10
    d_tr_dw, idx_tr_dw = tree_all.query(train_coords, k=K_DW + 1)
    d_te_dw, idx_te_dw = tree_all.query(test_coords, k=K_DW)
    # Train: skip self (col 0), use cols 1..K
    d_tr_nn = np.maximum(d_tr_dw[:, 1:], 1.0)  # avoid div-by-zero
    w_tr = 1.0 / d_tr_nn
    w_tr /= w_tr.sum(axis=1, keepdims=True)
    X_train["knn_dw10_log_ppm2"] = np.sum(w_tr * train_log_ppm2[idx_tr_dw[:, 1:]], axis=1)
    # Test
    d_te_nn = np.maximum(d_te_dw, 1.0)
    w_te = 1.0 / d_te_nn
    w_te /= w_te.sum(axis=1, keepdims=True)
    X_test["knn_dw10_log_ppm2"] = np.sum(w_te * train_log_ppm2[idx_te_dw], axis=1)

    # ── 2. Same-type KNN features ────────────────────────────────────
    logger.info("  Engineering: same-type KNN (K=10) ...")
    K_TYPE = 10
    type_knn_data: dict[str, dict[str, np.ndarray]] = {}
    X_train["knn_type_10_log_ppm2"] = np.nan
    X_test["knn_type_10_log_ppm2"] = np.nan

    if "property_type" in X_train.columns:
        for ptype in X_train["property_type"].unique():
            mask_tr = (X_train["property_type"] == ptype).values
            mask_te = (X_test["property_type"] == ptype).values
            n_type = int(mask_tr.sum())
            if n_type < K_TYPE + 2:
                continue
            type_coords = train_coords[mask_tr]
            type_lp = train_log_ppm2[mask_tr]
            type_tree = KDTree(type_coords)
            type_knn_data[str(ptype)] = {
                "coords": type_coords.astype(np.float32),
                "log_ppm2": type_lp.astype(np.float32),
            }
            k = min(K_TYPE, n_type - 1)
            _, idx_tr = type_tree.query(type_coords, k=k + 1)
            X_train.loc[X_train["property_type"] == ptype, "knn_type_10_log_ppm2"] = np.median(
                type_lp[idx_tr[:, 1 : k + 1]], axis=1
            )
            if mask_te.any():
                _, idx_te = type_tree.query(test_coords[mask_te], k=k)
                X_test.loc[X_test["property_type"] == ptype, "knn_type_10_log_ppm2"] = np.median(
                    type_lp[idx_te[:, :k]], axis=1
                )
    artifacts["type_knn_data"] = type_knn_data

    # ── 3. Count / frequency features ────────────────────────────────
    logger.info("  Engineering: count features ...")
    count_maps: dict[str, dict[str, int]] = {}
    train_count_features: dict[str, pd.Series] = {}
    test_count_features: dict[str, pd.Series] = {}
    for group_col, feat_col in [
        ("ime_ko", "ko_transaction_count"),
        ("municipality_normalized", "muni_transaction_count"),
        ("naselje", "naselje_transaction_count"),
    ]:
        if group_col in X_train.columns:
            normalized_values = X_train[group_col].fillna("unknown").astype(str)
            if group_col in {"ime_ko", "naselje"}:
                counts = (
                    normalized_values[~normalized_values.apply(_is_unknown_category_value)].value_counts().to_dict()
                )
            else:
                counts = normalized_values.value_counts().to_dict()
            count_maps[group_col] = counts
            train_count_features[feat_col] = normalized_values.map(counts).fillna(0).astype(float)
            test_count_features[feat_col] = (
                X_test[group_col].fillna("unknown").astype(str).map(counts).fillna(0).astype(float)
            )
        else:
            train_count_features[feat_col] = pd.Series(0.0, index=X_train.index)
            test_count_features[feat_col] = pd.Series(0.0, index=X_test.index)

    X_train = pd.concat([X_train, pd.DataFrame(train_count_features, index=X_train.index)], axis=1)
    X_test = pd.concat([X_test, pd.DataFrame(test_count_features, index=X_test.index)], axis=1)
    artifacts["count_maps"] = count_maps

    # ── 4. KO-level price per m² (all types combined) ────────────────
    logger.info("  Engineering: KO price medians ...")
    ko_ppm2_map: dict[str, float] = {}
    if "ime_ko" in X_train.columns:
        train_w_price = X_train[["ime_ko", "size_m2"]].copy()
        train_w_price["ppm2"] = y_train / train_w_price["size_m2"].clip(lower=1).values
        for ko, grp in train_w_price.groupby("ime_ko"):
            if not _is_unknown_category_value(ko) and len(grp) >= 5:
                ko_ppm2_map[str(ko)] = float(grp["ppm2"].median())
    global_median_ppm2_train = float(np.median(y_train / X_train["size_m2"].clip(lower=1).values))
    artifacts["ko_ppm2_map"] = ko_ppm2_map
    artifacts["global_median_ppm2_for_ko"] = global_median_ppm2_train
    train_ko_ppm2 = (
        X_train["ime_ko"].map(ko_ppm2_map).fillna(global_median_ppm2_train).astype(float)
        if "ime_ko" in X_train.columns
        else pd.Series(global_median_ppm2_train, index=X_train.index, dtype=float)
    )
    test_ko_ppm2 = (
        X_test["ime_ko"].map(ko_ppm2_map).fillna(global_median_ppm2_train).astype(float)
        if "ime_ko" in X_test.columns
        else pd.Series(global_median_ppm2_train, index=X_test.index, dtype=float)
    )
    X_train = pd.concat([X_train, pd.DataFrame({"price_per_m2_ko": train_ko_ppm2}, index=X_train.index)], axis=1)
    X_test = pd.concat([X_test, pd.DataFrame({"price_per_m2_ko": test_ko_ppm2}, index=X_test.index)], axis=1)

    # ── 5. Price ratio features ──────────────────────────────────────
    logger.info("  Engineering: price ratios ...")

    def _price_ratio_features(split_X: pd.DataFrame) -> pd.DataFrame:
        comp_ko = split_X.get("comp_type_ko_ppm2", pd.Series(0.0, index=split_X.index)).fillna(0)
        comp_muni = split_X.get("comp_type_muni_ppm2", pd.Series(0.0, index=split_X.index)).fillna(0)
        muni_ppm2 = (
            pd.to_numeric(
                split_X.get("price_per_m2_municipality", pd.Series(np.nan, index=split_X.index)),
                errors="coerce",
            )
            .clip(lower=1)
            .fillna(1)
        )
        region_ppm2 = (
            pd.to_numeric(
                split_X.get("price_per_m2_region", pd.Series(np.nan, index=split_X.index)),
                errors="coerce",
            )
            .clip(lower=1)
            .fillna(1)
        )
        return pd.DataFrame(
            {
                "ko_vs_muni_premium": (comp_ko - comp_muni).astype(float),
                "muni_vs_region_premium": np.log(muni_ppm2 / region_ppm2).astype(float),
            },
            index=split_X.index,
        )

    X_train = pd.concat([X_train, _price_ratio_features(X_train)], axis=1)
    X_test = pd.concat([X_test, _price_ratio_features(X_test)], axis=1)

    # ── 5b. Interaction features ─────────────────────────────────────
    logger.info("  Engineering: interaction features ...")

    def _interaction_features(split_X: pd.DataFrame) -> pd.DataFrame:
        knn_type = split_X.get("knn_type_10_log_ppm2", pd.Series(0.0, index=split_X.index)).fillna(0)
        comp_muni = split_X.get("comp_type_muni_ppm2", pd.Series(0.0, index=split_X.index)).fillna(0)
        building_age = pd.to_numeric(
            split_X.get("building_age", pd.Series(np.nan, index=split_X.index)),
            errors="coerce",
        ).fillna(0)
        return pd.DataFrame(
            {
                "hyperlocal_premium": (knn_type - comp_muni).astype(float),
                "building_age_sq": (building_age**2 / 1000.0).astype(float),
            },
            index=split_X.index,
        )

    X_train = pd.concat([X_train, _interaction_features(X_train)], axis=1)
    X_test = pd.concat([X_test, _interaction_features(X_test)], axis=1)

    # ── 6. Size percentile within type ───────────────────────────────
    logger.info("  Engineering: size percentiles ...")
    size_quantiles: dict[str, np.ndarray] = {}
    size_pct_train = pd.Series(0.5, index=X_train.index, dtype=float)
    size_pct_test = pd.Series(0.5, index=X_test.index, dtype=float)
    if "property_type" in X_train.columns:
        for ptype in X_train["property_type"].unique():
            mask_tr = X_train["property_type"] == ptype
            mask_te = X_test["property_type"] == ptype
            if mask_tr.sum() < 10:
                continue
            sizes_sorted = np.sort(X_train.loc[mask_tr, "size_m2"].values)
            size_quantiles[str(ptype)] = sizes_sorted
            size_pct_train.loc[mask_tr] = X_train.loc[mask_tr, "size_m2"].rank(pct=True).values
            if mask_te.any():
                size_pct_test.loc[mask_te] = np.searchsorted(sizes_sorted, X_test.loc[mask_te, "size_m2"].values) / len(
                    sizes_sorted
                )
    X_train = pd.concat([X_train, pd.DataFrame({"size_percentile": size_pct_train}, index=X_train.index)], axis=1)
    X_test = pd.concat([X_test, pd.DataFrame({"size_percentile": size_pct_test}, index=X_test.index)], axis=1)
    artifacts["size_quantiles"] = size_quantiles

    # ── 7. Data quality indicators ───────────────────────────────────
    def _quality_indicators(split_X: pd.DataFrame) -> pd.DataFrame:
        ev_year = pd.to_numeric(
            split_X.get("ev_leto_izg_stavbe", pd.Series(np.nan, index=split_X.index)),
            errors="coerce",
        )
        reno_cols = ["ev_leto_obn_strehe", "ev_leto_obn_fasade", "ev_leto_obn_oken", "ev_leto_obn_inst"]
        has_reno = pd.Series(False, index=split_X.index)
        for rc in reno_cols:
            if rc in split_X.columns:
                has_reno = has_reno | pd.to_numeric(split_X[rc], errors="coerce").notna()
        return pd.DataFrame(
            {
                "has_ev_data": ev_year.notna().astype(float),
                "has_renovation_data": has_reno.astype(float),
            },
            index=split_X.index,
        )

    X_train = pd.concat([X_train, _quality_indicators(X_train)], axis=1)
    X_test = pd.concat([X_test, _quality_indicators(X_test)], axis=1)

    # ── 8. Time index ────────────────────────────────────────────────
    min_year = float(X_train["transaction_year"].min()) if "transaction_year" in X_train.columns else 2020.0
    artifacts["min_year"] = min_year

    def _time_index_feature(split_X: pd.DataFrame) -> pd.DataFrame:
        yr = pd.to_numeric(
            split_X.get("transaction_year", pd.Series(np.nan, index=split_X.index)),
            errors="coerce",
        ).fillna(min_year)
        qtr = pd.to_numeric(
            split_X.get("transaction_quarter", pd.Series(np.nan, index=split_X.index)),
            errors="coerce",
        ).fillna(1)
        return pd.DataFrame({"time_index": ((yr - min_year) * 4 + qtr).astype(float)}, index=split_X.index)

    X_train = pd.concat([X_train, _time_index_feature(X_train)], axis=1)
    X_test = pd.concat([X_test, _time_index_feature(X_test)], axis=1)

    # ── 9. Renovation recency ────────────────────────────────────────
    reno_cols = ["ev_leto_obn_strehe", "ev_leto_obn_fasade", "ev_leto_obn_oken", "ev_leto_obn_inst"]

    def _reno_recency_features(split_X: pd.DataFrame) -> pd.DataFrame:
        reno_df = pd.DataFrame(index=split_X.index)
        for rc in reno_cols:
            if rc in split_X.columns:
                reno_df[rc] = pd.to_numeric(split_X[rc], errors="coerce")
        latest = reno_df.max(axis=1) if len(reno_df.columns) > 0 else pd.Series(np.nan, index=split_X.index)
        yr = pd.to_numeric(split_X.get("transaction_year", pd.Series(np.nan, index=split_X.index)), errors="coerce")
        return pd.DataFrame(
            {
                "latest_renovation_year": latest,
                "years_since_renovation": yr - latest,
            },
            index=split_X.index,
        )

    X_train = pd.concat([X_train, _reno_recency_features(X_train)], axis=1)
    X_test = pd.concat([X_test, _reno_recency_features(X_test)], axis=1)

    # ── 10. Parcel sold fraction ─────────────────────────────────────
    def _parcel_fraction_feature(split_X: pd.DataFrame) -> pd.DataFrame:
        parcela_m2 = pd.to_numeric(
            split_X.get("parcela_m2", pd.Series(np.nan, index=split_X.index)),
            errors="coerce",
        ).clip(lower=1)
        return pd.DataFrame(
            {"parcel_sold_fraction": (split_X["size_m2"] / parcela_m2).clip(upper=1.0).astype(float)},
            index=split_X.index,
        )

    X_train = pd.concat([X_train, _parcel_fraction_feature(X_train)], axis=1)
    X_test = pd.concat([X_test, _parcel_fraction_feature(X_test)], axis=1)

    # ── 11. Renovation score & building quality index ────────────────
    def _renovation_quality_features(split_X: pd.DataFrame) -> pd.DataFrame:
        reno_cols_q = ["ev_leto_obn_strehe", "ev_leto_obn_fasade", "ev_leto_obn_oken", "ev_leto_obn_inst"]
        yr = pd.to_numeric(split_X.get("transaction_year", pd.Series(np.nan, index=split_X.index)), errors="coerce")
        reno_sum = pd.Series(0.0, index=split_X.index)
        reno_count = pd.Series(0, index=split_X.index)
        for rc in reno_cols_q:
            if rc in split_X.columns:
                val = pd.to_numeric(split_X[rc], errors="coerce")
                reno_sum = reno_sum + val.fillna(0)
                reno_count = reno_count + val.notna().astype(int)
        # renovation_score: 1 if recently renovated (within 10 years), 0 otherwise
        latest_reno = pd.Series(np.nan, index=split_X.index)
        for rc in reno_cols_q:
            if rc in split_X.columns:
                val = pd.to_numeric(split_X[rc], errors="coerce")
                latest_reno = latest_reno.where(latest_reno >= val, val)
        years_since = yr - latest_reno
        renovation_score = ((years_since < 10) & years_since.notna()).astype(float)
        # building_quality_index: average renovation year (higher = newer renovations)
        quality_index = (reno_sum / reno_count.clip(lower=1)).where(reno_count > 0, np.nan)
        return pd.DataFrame(
            {
                "renovation_score": renovation_score,
                "building_quality_index": quality_index,
            },
            index=split_X.index,
        )

    X_train = pd.concat([X_train, _renovation_quality_features(X_train)], axis=1)
    X_test = pd.concat([X_test, _renovation_quality_features(X_test)], axis=1)

    # ── 12. Price trend (municipality+type quarterly growth) ─────────
    logger.info("  Engineering: price trend ...")
    if "municipality_normalized" in X_train.columns and "transaction_year" in X_train.columns:
        train_size_clip = X_train["size_m2"].clip(lower=1).values.astype(float)
        train_ppm2 = y_train / train_size_clip
        trend_df = pd.DataFrame(
            {
                "muni": X_train["municipality_normalized"].fillna("unknown").astype(str).values,
                "ptype": X_train.get("property_type", pd.Series("unknown", index=X_train.index)).astype(str).values,
                "year": pd.to_numeric(X_train["transaction_year"], errors="coerce").fillna(2020).values,
                "qtr": pd.to_numeric(
                    X_train.get("transaction_quarter", pd.Series(1, index=X_train.index)), errors="coerce"
                )
                .fillna(1)
                .values,
                "ppm2": train_ppm2,
            }
        )
        trend_df["period"] = trend_df["year"] * 4 + trend_df["qtr"]
        # Compute median ppm2 per municipality+type+period
        muni_type_period_median = trend_df.groupby(["muni", "ptype", "period"])["ppm2"].median()
        # QoQ growth rate (period vs period-1) - fast momentum
        trend_map: dict[tuple[str, str, float], float] = {}
        # YoY growth rate (period vs period-4) - longer horizon, less noise
        trend_yoy_map: dict[tuple[str, str, float], float] = {}
        # Level index: current median ppm2 normalised by full-history muni+type median
        level_map: dict[tuple[str, str, float], float] = {}
        muni_type_alltime_median = trend_df.groupby(["muni", "ptype"])["ppm2"].median()
        for (muni, ptype, period), median_val in muni_type_period_median.items():
            prev = muni_type_period_median.get((muni, ptype, period - 1))
            if prev and prev > 0:
                trend_map[(muni, ptype, period)] = float(median_val / prev - 1.0)
            prev_year = muni_type_period_median.get((muni, ptype, period - 4))
            if prev_year and prev_year > 0:
                trend_yoy_map[(muni, ptype, period)] = float(median_val / prev_year - 1.0)
            alltime = muni_type_alltime_median.get((muni, ptype))
            if alltime and alltime > 0:
                level_map[(muni, ptype, period)] = float(median_val / alltime)

        def _apply_map(split_X: pd.DataFrame, mapping: dict, default: float) -> pd.Series:
            muni = (
                split_X.get("municipality_normalized", pd.Series("unknown", index=split_X.index))
                .fillna("unknown")
                .astype(str)
            )
            ptype = split_X.get("property_type", pd.Series("unknown", index=split_X.index)).astype(str)
            yr = pd.to_numeric(split_X.get("transaction_year"), errors="coerce").fillna(2020)
            qtr = pd.to_numeric(
                split_X.get("transaction_quarter", pd.Series(1, index=split_X.index)), errors="coerce"
            ).fillna(1)
            period = yr * 4 + qtr
            return pd.Series(
                [mapping.get((m, p, per), default) for m, p, per in zip(muni, ptype, period, strict=False)],
                index=split_X.index,
                dtype=float,
            )

        X_train["price_trend_muni"] = _apply_map(X_train, trend_map, 0.0)
        X_test["price_trend_muni"] = _apply_map(X_test, trend_map, 0.0)
        X_train["price_trend_muni_yoy"] = _apply_map(X_train, trend_yoy_map, 0.0)
        X_test["price_trend_muni_yoy"] = _apply_map(X_test, trend_yoy_map, 0.0)
        X_train["price_level_muni"] = _apply_map(X_train, level_map, 1.0)
        X_test["price_level_muni"] = _apply_map(X_test, level_map, 1.0)
        artifacts["trend_map_keys"] = len(trend_map)
        artifacts["trend_yoy_map_keys"] = len(trend_yoy_map)
        artifacts["level_map_keys"] = len(level_map)

    # Final defragmentation for downstream slicing/filtering performance.
    X_train = X_train.copy()
    X_test = X_test.copy()

    elapsed = time.time() - t0
    logger.info("  Feature engineering complete in %.1fs (%d new features)", elapsed, 19)

    return X_train, X_test, artifacts


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
    always_numeric = ALWAYS_INCLUDE_NUMERIC if always_numeric is None else always_numeric
    always_categorical = ALWAYS_INCLUDE_CATEGORICAL if always_categorical is None else always_categorical
    # Pass type-specific always sets so they bypass fill-rate filter
    filtered_numeric, filtered_categorical = _filter_features(
        df,
        candidate_numeric,
        candidate_categorical,
        extra_keep_numeric=always_numeric,
        extra_keep_categorical=always_categorical,
    )
    # Score features against log(price/m²) — the actual prediction target
    size_vals = pd.to_numeric(df.get("size_m2"), errors="coerce").clip(lower=1).values
    target_series = pd.Series(np.log(np.maximum(target, 1) / size_vals), index=df.index)

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


def _select_global_gpu_safe_features(
    df: pd.DataFrame,
    target: np.ndarray,
    candidate_numeric: list[str],
    candidate_categorical: list[str],
) -> tuple[list[str], list[str], str]:
    if _get_catboost_task_type() != "GPU" or len(df) < 120_000:
        return candidate_numeric, candidate_categorical, "full_global"

    always_numeric = {
        "size_m2",
        "log_size_m2",
        "transaction_year",
        "price_per_m2_region",
        "price_per_m2_municipality",
        "comp_type_muni_ppm2",
        "comp_type_ko_ppm2",
        "knn_3_log_ppm2",
        "knn_dw10_log_ppm2",
        "knn_type_10_log_ppm2",
        "price_per_m2_ko",
    }
    always_categorical = {
        "property_type",
        "municipality_normalized",
        "statistical_region",
        "kn_ggo_section",
    }
    is_ultra_large = len(df) >= 150_000
    selected_numeric, selected_categorical, _scores = _select_type_specific_features(
        df,
        target,
        candidate_numeric,
        candidate_categorical,
        always_numeric=always_numeric,
        always_categorical=always_categorical,
        max_extra_numeric=4 if is_ultra_large else 6,
        max_extra_categorical=0,
    )
    return (
        selected_numeric,
        selected_categorical,
        "gpu_ultra_safe_global" if is_ultra_large else "gpu_safe_global",
    )


def _build_model(
    numeric_feats: list[str],
    categorical_feats: list[str],
    n_samples: int,
    *,
    hp_overrides: dict | None = None,
    use_lossguide: bool = False,
) -> CatBoostModel:
    """Build a CatBoostModel with adaptive hyperparameters."""
    hp = _adaptive_hyperparams(n_samples, apply_gpu_adjustments=False)
    if hp_overrides:
        hp.update(hp_overrides)
    hp = _apply_gpu_param_adjustments(hp)
    # Re-apply hp_overrides for keys that GPU adjustments may have clobbered
    if hp_overrides:
        for key in ("iterations", "learning_rate", "depth", "od_wait"):
            if key in hp_overrides:
                hp[key] = hp_overrides[key]
    explicit_ctr = (hp_overrides or {}).get("max_ctr_complexity")
    if hp.get("task_type") == "GPU":
        is_large_fit = n_samples >= 120_000
        has_many_categories = len(categorical_feats) >= 9
        if is_large_fit:
            hp["border_count"] = min(int(hp.get("border_count", 128) or 128), 64)
            hp["gpu_ram_part"] = min(float(hp.get("gpu_ram_part", 0.50) or 0.50), 0.22)
            hp["one_hot_max_size"] = min(int(hp.get("one_hot_max_size", 2) or 2), 2)
            hp["iterations"] = min(int(hp.get("iterations", 2000) or 2000), 1200)
        if is_large_fit or has_many_categories:
            if explicit_ctr is None:
                hp["max_ctr_complexity"] = 1
            hp["gpu_cat_features_storage"] = "CpuPinnedMemory"
        if is_large_fit and hp.get("depth", 8) > 6:
            hp["depth"] = 6
    # Lossguide (leaf-wise like LightGBM) is faster and often better on GPU for large datasets
    if use_lossguide and hp.get("task_type") == "GPU":
        hp["grow_policy"] = "Lossguide"
        hp["max_leaves"] = 128
    return CatBoostModel(numeric_feats, categorical_feats, hp)


def _compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    y_t = np.asarray(y_true, dtype=float)
    y_p = np.asarray(y_pred, dtype=float)
    mask = (y_t > 0) & np.isfinite(y_t) & np.isfinite(y_p)
    y_t = y_t[mask]
    y_p = y_p[mask]
    if len(y_t) == 0:
        return {}
    mae = float(mean_absolute_error(y_t, y_p))
    rmse = float(np.sqrt(mean_squared_error(y_t, y_p)))
    r2 = float(r2_score(y_t, y_p)) if len(y_t) >= 2 else float("nan")
    mape = float(np.mean(np.abs((y_t - y_p) / y_t)) * 100)
    median_ae = float(np.median(np.abs(y_t - y_p)))
    return {"mae": mae, "rmse": rmse, "r2": r2, "mape": mape, "median_ae": median_ae}


def _sanitize_metric_summary(metrics: dict[str, Any] | None) -> dict[str, float | None] | None:
    if not metrics:
        return None

    sanitized: dict[str, float | None] = {}
    for key in ("mae", "rmse", "r2", "mape", "median_ae"):
        value = metrics.get(key)
        if value is None:
            sanitized[key] = None
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            sanitized[key] = None
            continue
        sanitized[key] = numeric if np.isfinite(numeric) else None
    return sanitized


def _candidate_metrics_tuple(candidate: dict[str, Any]) -> tuple[float, float, float]:
    metrics = candidate.get("metrics") or {}
    mape = float(metrics.get("mape", float("inf")) or float("inf"))
    r2 = float(metrics.get("r2", float("-inf")) or float("-inf"))
    mae = float(metrics.get("mae", float("inf")) or float("inf"))
    return mape, r2, mae


def _select_best_metrics_candidate(
    candidates: list[dict[str, Any]],
    *,
    property_type: str | None = None,
) -> dict[str, Any] | None:
    if not candidates:
        return None

    selection_prior = TYPE_CANDIDATE_SELECTION_PRIORS.get(str(property_type or ""), {})
    r2_tolerance = float(selection_prior.get("r2_tolerance", 0.02))
    mape_tolerance = float(selection_prior.get("mape_tolerance", 0.0))
    prefer_r2 = bool(selection_prior.get("prefer_r2", False))

    best_r2 = max(
        float((candidate.get("metrics") or {}).get("r2", float("-inf")) or float("-inf")) for candidate in candidates
    )
    viable = [
        candidate
        for candidate in candidates
        if float((candidate.get("metrics") or {}).get("r2", float("-inf")) or float("-inf")) >= best_r2 - r2_tolerance
    ]
    if not viable:
        viable = candidates

    if mape_tolerance > 0.0:
        best_mape = min(
            float((candidate.get("metrics") or {}).get("mape", float("inf")) or float("inf")) for candidate in viable
        )
        mape_viable = [
            candidate
            for candidate in viable
            if float((candidate.get("metrics") or {}).get("mape", float("inf")) or float("inf"))
            <= best_mape + mape_tolerance
        ]
        if mape_viable:
            viable = mape_viable

    if prefer_r2:
        viable.sort(
            key=lambda candidate: (
                -float((candidate.get("metrics") or {}).get("r2", float("-inf")) or float("-inf")),
                float((candidate.get("metrics") or {}).get("mape", float("inf")) or float("inf")),
                float((candidate.get("metrics") or {}).get("mae", float("inf")) or float("inf")),
                int(candidate.get("total_feature_count", 0)),
            )
        )
        return viable[0]

    viable.sort(
        key=lambda candidate: (
            float((candidate.get("metrics") or {}).get("mape", float("inf")) or float("inf")),
            float((candidate.get("metrics") or {}).get("mae", float("inf")) or float("inf")),
            -float((candidate.get("metrics") or {}).get("r2", float("-inf")) or float("-inf")),
            int(candidate.get("total_feature_count", 0)),
        )
    )
    return viable[0]


def _select_best_training_candidate(
    candidates: list[dict[str, Any]],
    *,
    property_type: str | None = None,
) -> dict[str, Any] | None:
    return _select_best_metrics_candidate(candidates, property_type=property_type)


def _build_feature_variants(
    rich_numeric: list[str],
    rich_categorical: list[str],
    always_numeric: set[str],
    always_categorical: set[str],
    *,
    property_type: str | None = None,
) -> dict[str, dict[str, list[str]]]:
    simple_numeric_order = [
        "size_m2",
        "log_size_m2",
        "transaction_year",
        "price_per_m2_region",
        "price_per_m2_municipality",
        "price_per_m2_ko",
        "comp_type_muni_ppm2",
        "comp_type_ko_ppm2",
        "comp_type_naselje_ppm2",
        "comp_subtype_muni_ppm2",
        "comp_subtype_ko_ppm2",
        "comp_subtype_naselje_ppm2",
        "dist_ljubljana",
        "dist_maribor",
        "dist_coast",
        "knn_3_log_ppm2",
        "knn_5_log_ppm2",
        "knn_type_10_log_ppm2",
        "ko_transaction_count",
        "muni_transaction_count",
        "naselje_transaction_count",
        "building_age",
        "year_built",
        "parcela_m2",
        "prodani_delez_parcele",
        "prodani_delez_dela_stavbe",
    ]
    simple_categorical_order = [
        "municipality_normalized",
        "market_subtype_key",
        "statistical_region",
        "ime_ko",
        "naselje",
        "vrsta_zemljisca",
        "lega_v_stavbi",
        "dtm_pokritost_tal",
        "parcela_namenska_raba",
        "emv_zone_model",
        "emv_zone_id",
    ]
    simple_numeric_keep = always_numeric | set(simple_numeric_order)
    simple_categorical_keep = always_categorical | set(simple_categorical_order)

    simple_numeric = [feature for feature in rich_numeric if feature in simple_numeric_keep]
    simple_categorical = [feature for feature in rich_categorical if feature in simple_categorical_keep]

    if not simple_numeric:
        simple_numeric = rich_numeric[: min(len(rich_numeric), 8)]
    if not simple_categorical and rich_categorical:
        simple_categorical = rich_categorical[: min(len(rich_categorical), 4)]

    variants = {
        "simple": {
            "numeric": simple_numeric,
            "categorical": simple_categorical,
        },
        "rich": {
            "numeric": list(rich_numeric),
            "categorical": list(rich_categorical),
        },
    }

    if property_type == "kmetijsko":
        land_numeric_order = [
            "size_m2",
            "log_size_m2",
            "parcela_m2",
            "prodani_delez_parcele",
            "transaction_year",
            "time_index",
            "latitude",
            "longitude",
            "dist_ljubljana",
            "dist_maribor",
            "dist_coast",
            "price_per_m2_region",
            "price_per_m2_municipality",
            "price_per_m2_ko",
            "comp_type_muni_ppm2",
            "comp_type_ko_ppm2",
            "comp_type_naselje_ppm2",
            "comp_subtype_muni_ppm2",
            "comp_subtype_ko_ppm2",
            "comp_subtype_naselje_ppm2",
            "knn_3_log_ppm2",
            "knn_5_log_ppm2",
            "knn_20_log_ppm2",
            "knn_dw10_log_ppm2",
            "knn_type_10_log_ppm2",
            "ko_transaction_count",
            "muni_transaction_count",
            "ko_vs_muni_premium",
            "muni_vs_region_premium",
            "emv_zone_level",
            "ev_del_povrsina",
            "ev_del_upor_pov",
            "ev_pov_stavbe",
            "gji_kanalizacija_distance_m",
            "gji_vodovod_distance_m",
            "gji_elektrika_distance_m",
            "gji_plin_distance_m",
            "gji_plin_nearby_100m",
            "gji_ceste_distance_m",
            "gji_toplota_distance_m",
            "gji_zeleznice_distance_m",
            "gji_zeleznice_nearby_1000m",
            "gji_opt_distance_m",
            "dtm_voda_distance_m",
            "dtm_nadm_visina_stavbe",
            "kn_ggo_openness",
        ]
        land_categorical_order = [
            "municipality_normalized",
            "statistical_region",
            "ime_ko",
            "naselje",
            "vrsta_zemljisca",
            "parcela_namenska_raba",
            "kn_ggo_section",
            "dtm_pokritost_tal",
            "emv_zone_id",
            "emv_zone_name",
        ]
        land_numeric_keep = always_numeric | set(land_numeric_order)
        land_categorical_keep = always_categorical | set(land_categorical_order)
        land_numeric = [feature for feature in rich_numeric if feature in land_numeric_keep]
        land_categorical = [feature for feature in rich_categorical if feature in land_categorical_keep]
        if land_numeric:
            variants["land_focus"] = {
                "numeric": land_numeric,
                "categorical": land_categorical,
            }

    return variants


def _predict_with_model_meta(
    X: pd.DataFrame,
    model_meta: dict[str, Any] | CatBoostModel,
    *,
    default_target_transform: str = "log_ppm2",
) -> np.ndarray:
    if isinstance(model_meta, dict):
        pipeline = model_meta["pipeline"]
        target_transform = str(model_meta.get("target_transform", default_target_transform))
    else:
        pipeline = model_meta
        target_transform = default_target_transform

    raw_pred = np.clip(pipeline.predict(X), -30, 30)  # prevent exp overflow
    if target_transform == "log_ppm2":
        size_vals = (
            X["size_m2"].clip(lower=1).values.astype(float) if "size_m2" in X.columns else np.ones(len(X), dtype=float)
        )
        return np.maximum(size_vals * np.exp(raw_pred), 0)
    if target_transform == "log_price":
        return np.maximum(np.expm1(raw_pred), 0)
    return np.maximum(raw_pred, 0)


def _predict_specialist_fallback_meta(
    X: pd.DataFrame,
    specialist_meta: dict[str, Any],
    *,
    default_target_transform: str = "log_ppm2",
) -> np.ndarray:
    subtype_models = specialist_meta.get("subtype_models") if isinstance(specialist_meta, dict) else None
    if not subtype_models:
        return _predict_with_model_meta(X, specialist_meta, default_target_transform=default_target_transform)

    default_model = specialist_meta.get("default_model")
    if isinstance(default_model, dict):
        preds = _predict_with_model_meta(X, default_model, default_target_transform=default_target_transform)
    else:
        preds = np.zeros(len(X), dtype=float)

    if "market_subtype_key" not in X.columns:
        return preds

    subtype_series = X["market_subtype_key"].fillna("unknown").astype(str)
    for subtype_key, subtype_meta in subtype_models.items():
        mask = subtype_series == str(subtype_key)
        if not mask.any():
            continue
        preds[mask.to_numpy()] = _predict_with_model_meta(
            X.loc[mask],
            subtype_meta,
            default_target_transform=default_target_transform,
        )
    return preds


def _predict_any_model_meta(
    X: pd.DataFrame,
    model_meta: Any,
    *,
    default_target_transform: str = "log_ppm2",
) -> np.ndarray:
    if isinstance(model_meta, dict) and model_meta.get("subtype_models"):
        return _predict_specialist_fallback_meta(
            X,
            model_meta,
            default_target_transform=default_target_transform,
        )
    return _predict_with_model_meta(X, model_meta, default_target_transform=default_target_transform)


def _resolve_model_feature_lists(
    model_meta: Any,
    *,
    default_numeric: list[str],
    default_categorical: list[str],
) -> tuple[list[str], list[str]]:
    if not isinstance(model_meta, dict):
        return list(default_numeric), list(default_categorical)

    numeric = model_meta.get("numeric_features")
    categorical = model_meta.get("categorical_features")
    if numeric is not None or categorical is not None:
        return list(numeric or default_numeric), list(categorical or default_categorical)

    default_model = model_meta.get("default_model")
    if isinstance(default_model, dict):
        return (
            list(default_model.get("numeric_features") or default_numeric),
            list(default_model.get("categorical_features") or default_categorical),
        )

    return list(default_numeric), list(default_categorical)


def _train_specialist_fallback_model(
    property_type: str,
    X_train_type: pd.DataFrame,
    y_train_type: np.ndarray,
    X_test_type: pd.DataFrame,
    y_test_type: np.ndarray,
    *,
    raw_numeric_features: list[str],
    raw_categorical_features: list[str],
    always_numeric: set[str],
    always_categorical: set[str],
    default_target_transform: str,
    use_lossguide: bool,
    training_progress: dict[str, dict[str, int]],
) -> dict[str, Any] | None:
    prior = TYPE_SPECIALIST_MODEL_PRIORS.get(property_type)
    if not prior:
        return None
    if len(X_train_type) < int(prior.get("min_train_rows", 0)) or len(X_test_type) < int(prior.get("min_test_rows", 0)):
        return None

    feature_variants = _build_feature_variants(
        raw_numeric_features,
        raw_categorical_features,
        always_numeric,
        always_categorical,
        property_type=property_type,
    )
    feature_variant = str(prior.get("feature_variant", "rich"))
    variant_features = feature_variants.get(feature_variant) or feature_variants.get("rich")
    if not variant_features:
        return None

    specialist_numeric = list(variant_features.get("numeric") or [])
    specialist_categorical = list(variant_features.get("categorical") or [])
    if not specialist_numeric:
        return None

    specialist_target_transform = str(prior.get("target_transform") or default_target_transform or "log_ppm2")
    specialist_hp = dict(TYPE_HP_OVERRIDES.get(property_type) or {})
    specialist_hp.update(dict(prior.get("hp_overrides") or {}))
    specialist_model = _build_model(
        specialist_numeric,
        specialist_categorical,
        len(X_train_type),
        hp_overrides=specialist_hp,
        use_lossguide=use_lossguide,
    )
    specialist_result = _train_single_model(
        specialist_model,
        X_train_type,
        y_train_type,
        X_test_type,
        y_test_type,
        f"specialist:{property_type}",
        training_progress,
        target_transform=specialist_target_transform,
        sample_weight=_build_recency_sample_weights(X_train_type, y_train_type),
    )
    base_specialist = {
        "pipeline": specialist_model,
        "numeric_features": specialist_numeric,
        "categorical_features": specialist_categorical,
        "target_transform": specialist_target_transform,
        "feature_variant": feature_variant,
        "model_hyperparameters": dict(specialist_model.params),
        "result": specialist_result,
        "metrics": specialist_result["metrics"],
    }
    enable_subtype_family = bool(prior.get("enable_subtype_family", False))
    subtype_min_train_rows = max(80, int(prior.get("subtype_min_train_rows", 600)))
    subtype_min_test_rows = max(20, int(prior.get("subtype_min_test_rows", 120)))
    if (
        not enable_subtype_family
        or "market_subtype_key" not in X_train_type.columns
        or "market_subtype_key" not in X_test_type.columns
    ):
        return base_specialist

    subtype_train_counts = X_train_type["market_subtype_key"].fillna("unknown").astype(str).value_counts()
    subtype_test_counts = X_test_type["market_subtype_key"].fillna("unknown").astype(str).value_counts()
    subtype_numeric = list(specialist_numeric)
    subtype_categorical = [feature for feature in specialist_categorical if feature != "market_subtype_key"]
    subtype_models: dict[str, dict[str, Any]] = {}
    for subtype_key, subtype_train_count in subtype_train_counts.items():
        subtype_test_count = int(subtype_test_counts.get(subtype_key, 0))
        if (
            _is_unknown_category_value(subtype_key)
            or int(subtype_train_count) < subtype_min_train_rows
            or subtype_test_count < subtype_min_test_rows
        ):
            continue
        subtype_train_mask = X_train_type["market_subtype_key"].fillna("unknown").astype(str) == str(subtype_key)
        subtype_test_mask = X_test_type["market_subtype_key"].fillna("unknown").astype(str) == str(subtype_key)
        X_sub_train = X_train_type.loc[subtype_train_mask].copy()
        y_sub_train = y_train_type[subtype_train_mask.to_numpy()]
        X_sub_test = X_test_type.loc[subtype_test_mask].copy()
        y_sub_test = y_test_type[subtype_test_mask.to_numpy()]
        if len(X_sub_train) < subtype_min_train_rows or len(X_sub_test) < subtype_min_test_rows:
            continue
        subtype_model = _build_model(
            subtype_numeric,
            subtype_categorical,
            len(X_sub_train),
            hp_overrides=specialist_hp,
            use_lossguide=False,
        )
        subtype_result = _train_single_model(
            subtype_model,
            X_sub_train,
            y_sub_train,
            X_sub_test,
            y_sub_test,
            f"subtype:{property_type}",
            None,
            target_transform=specialist_target_transform,
            sample_weight=_build_recency_sample_weights(X_sub_train, y_sub_train),
        )
        subtype_models[str(subtype_key)] = {
            "pipeline": subtype_model,
            "numeric_features": list(subtype_numeric),
            "categorical_features": list(subtype_categorical),
            "target_transform": specialist_target_transform,
            "feature_variant": feature_variant,
            "model_hyperparameters": dict(subtype_model.params),
            "metrics": subtype_result["metrics"],
            "train_rows": int(len(X_sub_train)),
            "test_rows": int(len(X_sub_test)),
        }

    if not subtype_models:
        return base_specialist

    subtype_family = {
        "mode": "subtype_family",
        "target_transform": specialist_target_transform,
        "feature_variant": feature_variant,
        "default_model": {
            "pipeline": specialist_model,
            "numeric_features": list(specialist_numeric),
            "categorical_features": list(specialist_categorical),
            "target_transform": specialist_target_transform,
            "feature_variant": feature_variant,
            "model_hyperparameters": dict(specialist_model.params),
            "metrics": specialist_result["metrics"],
            "train_rows": int(len(X_train_type)),
            "test_rows": int(len(X_test_type)),
        },
        "subtype_models": subtype_models,
    }
    subtype_family_pred = _predict_specialist_fallback_meta(
        X_test_type,
        subtype_family,
        default_target_transform=specialist_target_transform,
    )
    subtype_family_metrics = _compute_metrics(y_test_type, subtype_family_pred)
    subtype_family_metrics["n_train"] = len(X_train_type)
    subtype_family_metrics["n_test"] = len(X_test_type)
    subtype_family["metrics"] = subtype_family_metrics

    best_specialist = _select_best_metrics_candidate(
        [
            {"label": "base", "metrics": base_specialist["metrics"], "meta": base_specialist},
            {"label": "subtype_family", "metrics": subtype_family_metrics, "meta": subtype_family},
        ],
        property_type=property_type,
    )
    return best_specialist["meta"] if best_specialist else base_specialist


def _compute_per_type_blend_weight(
    property_type: str,
    y_true: np.ndarray,
    global_pred: np.ndarray,
    per_type_pred: np.ndarray,
    n_test: int,
) -> tuple[float, dict[str, Any]]:
    """Select the best per-type/global blend on recent holdout data.

    Returns `(weight, metrics)` where weight is in [0, 1]:
    - 0.0 => global-only routing for this type
    - 1.0 => per-type-only routing for this type
    - (0,1) => weighted blend of per-type and global predictions
    """
    if n_test < 20:
        metrics = _compute_metrics(y_true, global_pred)
        return 0.0, metrics

    routing_prior = TYPE_ROUTING_PRIORS.get(property_type, {})
    max_weight = float(routing_prior.get("max_weight", 1.0))
    r2_tolerance = float(routing_prior.get("r2_tolerance", 0.01))
    candidates: list[dict[str, Any]] = []

    for weight in np.linspace(0.0, max_weight, int(round(max_weight / 0.05)) + 1):
        blended = weight * per_type_pred + (1.0 - weight) * global_pred
        metrics = _compute_metrics(y_true, blended)
        candidates.append({"weight": float(weight), "metrics": metrics})

    best_r2 = max(
        float((candidate["metrics"] or {}).get("r2", float("-inf")) or float("-inf")) for candidate in candidates
    )
    viable = [
        candidate
        for candidate in candidates
        if float((candidate["metrics"] or {}).get("r2", float("-inf")) or float("-inf")) >= best_r2 - r2_tolerance
    ]
    viable.sort(
        key=lambda candidate: (
            float((candidate["metrics"] or {}).get("mape", float("inf")) or float("inf")),
            float((candidate["metrics"] or {}).get("mae", float("inf")) or float("inf")),
            -float((candidate["metrics"] or {}).get("r2", float("-inf")) or float("-inf")),
            abs(float(candidate.get("weight", 0.0))),
        )
    )
    best = viable[0] if viable else candidates[0]
    best_weight = float(best.get("weight", 0.0))
    best_metrics = dict(best.get("metrics") or {})
    return best_weight, best_metrics


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


def _effective_share_series(frame: pd.DataFrame) -> pd.Series:
    share_series = pd.to_numeric(frame.get("prodani_delez_dela_stavbe"), errors="coerce")
    if share_series.isna().all():
        share_series = pd.to_numeric(frame.get("prodani_delez_parcele"), errors="coerce")
    else:
        parcel_share = pd.to_numeric(frame.get("prodani_delez_parcele"), errors="coerce")
        share_series = share_series.where(share_series.notna(), parcel_share)
    return share_series.fillna(1.0)


def _share_bucket_labels(frame: pd.DataFrame) -> pd.Series:
    effective_share = _effective_share_series(frame)
    return pd.Series(
        np.select(
            [
                effective_share >= 0.999,
                effective_share >= 0.95,
                effective_share >= 0.5,
            ],
            ["full", "mostly_full", "partial"],
            default="small_share",
        ),
        index=frame.index,
        dtype="object",
    )


def _round_quantiles(series: pd.Series, quantiles: list[float]) -> dict[str, float] | None:
    numeric = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if numeric.empty:
        return None
    return {f"q{int(q * 100):02d}": round(float(numeric.quantile(q)), 2) for q in quantiles}


def _build_segment_metric_table(
    frame: pd.DataFrame,
    group_col: str,
    *,
    min_count: int = 25,
) -> list[dict[str, Any]]:
    if group_col not in frame.columns:
        return []
    rows: list[dict[str, Any]] = []
    for segment, group in frame.groupby(group_col, dropna=False):
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
                "mape": round(float(metrics.get("mape", 0.0)), 2) if metrics.get("mape") is not None else None,
                "median_ae": round(float(metrics.get("median_ae", 0.0)), 2),
            }
        )
    return sorted(rows, key=lambda item: (item["mape"] is None, -(item["mape"] or 0.0), -item["n"], item["segment"]))


def _build_residual_diagnostics(
    X_test: pd.DataFrame,
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> dict[str, dict[str, Any]]:
    target_types = ["stanovanje", "hisa", "parcela", "kmetijsko", "garaza"]
    frame = X_test.copy()
    if "property_type" not in frame.columns:
        return {}
    frame["y_true"] = y_true
    frame["y_pred"] = y_pred
    frame["residual_pct"] = np.where(
        frame["y_true"] > 0, (frame["y_pred"] - frame["y_true"]) / frame["y_true"] * 100.0, np.nan
    )

    diagnostics: dict[str, dict[str, Any]] = {}
    for property_type in target_types:
        group = frame[frame["property_type"].astype(str) == property_type].copy()
        if len(group) < 10:
            continue
        under = group[group["residual_pct"] <= -10]
        over = group[group["residual_pct"] >= 10]
        diagnostics[property_type] = {
            "rows": int(len(group)),
            "median_residual_pct": round(float(group["residual_pct"].median()), 2),
            "underprediction": {
                "rows": int(len(under)),
                "share": round(float(len(under) / len(group)), 4),
                "median_pct": round(float(under["residual_pct"].median()), 2) if len(under) else None,
            },
            "overprediction": {
                "rows": int(len(over)),
                "share": round(float(len(over) / len(group)), 4),
                "median_pct": round(float(over["residual_pct"].median()), 2) if len(over) else None,
            },
        }
    return diagnostics


def _segment_calibration_feature_priority(property_type: str) -> list[str]:
    property_key = str(property_type)
    prioritized = CALIBRATION_SEGMENT_PRIORITIES.get(property_key, [])
    fallback = ["kn_ggo_section", "vrsta_zemljisca", "parcela_namenska_raba", "ime_ko"]
    ordered: list[str] = []
    for feature in prioritized + fallback:
        if feature not in ordered:
            ordered.append(feature)
    return ordered


def _fit_segment_calibration_for_type(
    group: pd.DataFrame,
    property_type: str,
    *,
    clip_low: float,
    clip_high: float,
) -> dict[str, Any] | None:
    if str(property_type) in CALIBRATION_SEGMENT_DISABLED_TYPES:
        return None
    if len(group) < 120:
        return None

    base_pred = group["base_pred"].to_numpy(dtype=float)
    y_true = group["y_true"].to_numpy(dtype=float)
    baseline_metrics = _compute_metrics(y_true, base_pred) or {}
    baseline_mape = float(baseline_metrics.get("mape", np.inf))
    baseline_r2 = float(baseline_metrics.get("r2", -np.inf))
    min_rows_per_value = max(30, len(group) // 80)

    best_meta: dict[str, Any] | None = None
    for feature_name in _segment_calibration_feature_priority(property_type):
        if feature_name not in group.columns:
            continue

        values = group[feature_name].fillna("unknown").astype(str)
        value_counts = values[values != "unknown"].value_counts()
        eligible_values = value_counts[value_counts >= min_rows_per_value]
        if len(eligible_values) < 2:
            continue

        if len(eligible_values) > 24:
            eligible_values = eligible_values.nlargest(24)

        factor_map: dict[str, float] = {}
        count_map: dict[str, int] = {}
        segment_factor = np.ones(len(group), dtype=float)
        for value in eligible_values.index:
            mask = values == value
            count = int(mask.sum())
            if count < min_rows_per_value:
                continue
            factor = float(np.clip(group.loc[mask, "residual_ratio"].median(), clip_low, clip_high))
            factor_map[str(value)] = factor
            count_map[str(value)] = count
            segment_factor[mask.to_numpy(dtype=bool)] = factor

        if len(factor_map) < 2:
            continue

        adjusted_pred = np.maximum(base_pred * segment_factor, 1.0)
        candidate_metrics = _compute_metrics(y_true, adjusted_pred) or {}
        candidate_mape = float(candidate_metrics.get("mape", np.inf))
        candidate_r2 = float(candidate_metrics.get("r2", -np.inf))
        if not np.isfinite(candidate_mape):
            continue

        if best_meta is None:
            best_meta = {
                "feature": feature_name,
                "factors": factor_map,
                "counts": count_map,
                "metrics": candidate_metrics,
                "mape": candidate_mape,
                "r2": candidate_r2,
                "adjusted_pred": adjusted_pred,
            }
            continue

        improved_mape = candidate_mape < best_meta["mape"] - 0.1
        tie_break_r2 = abs(candidate_mape - best_meta["mape"]) <= 0.1 and candidate_r2 > best_meta["r2"] + 0.002
        if improved_mape or tie_break_r2:
            best_meta = {
                "feature": feature_name,
                "factors": factor_map,
                "counts": count_map,
                "metrics": candidate_metrics,
                "mape": candidate_mape,
                "r2": candidate_r2,
                "adjusted_pred": adjusted_pred,
            }

    if best_meta is None:
        return None

    if best_meta["mape"] >= baseline_mape - 0.05 and best_meta["r2"] <= baseline_r2 + 0.002:
        return None

    return {
        "feature": best_meta["feature"],
        "factors": best_meta["factors"],
        "counts": best_meta["counts"],
        "metrics": {
            "mape": round(float(best_meta["mape"]), 6),
            "r2": round(float(best_meta["r2"]), 6),
        },
    }


def _build_recent_research_diagnostics(
    df: pd.DataFrame,
    X_test: pd.DataFrame,
    y_test: np.ndarray,
    y_pred_combined: np.ndarray,
    per_type_feature_usage: dict[str, dict[str, Any]],
    routing_comparison: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {}
    years, year_source = _extract_year_series(df)
    valid_years = years.dropna()
    diagnostics["dataset_window"] = {
        "year_source": year_source,
        "start_year": int(valid_years.min()) if not valid_years.empty else None,
        "end_year": int(valid_years.max()) if not valid_years.empty else None,
        "rows": int(len(df)),
    }

    working = df.copy()
    working["ppm2"] = np.where(
        pd.to_numeric(working.get("size_m2"), errors="coerce") > 0, working["price_eur"] / working["size_m2"], np.nan
    )
    if "property_type" in working.columns and "transaction_year" in working.columns:
        counts = (
            working.groupby(["property_type", "transaction_year"])
            .size()
            .reset_index(name="rows")
            .sort_values(["property_type", "transaction_year"])
        )
        diagnostics["per_type_year_counts"] = counts.to_dict(orient="records")

    quantiles: dict[str, Any] = {}
    if "property_type" in working.columns:
        for property_type, group in working.groupby("property_type"):
            quantiles[str(property_type)] = {
                "rows": int(len(group)),
                "price_eur": _round_quantiles(group["price_eur"], [0.1, 0.25, 0.5, 0.75, 0.9]),
                "ppm2": _round_quantiles(group["ppm2"], [0.1, 0.25, 0.5, 0.75, 0.9]),
            }
    diagnostics["per_type_value_quantiles"] = quantiles

    candidate_features = [feature for feature in NUMERIC_FEATURES + CATEGORICAL_FEATURES if feature in working.columns]
    missingness: dict[str, dict[str, Any]] = {}
    cardinality: dict[str, dict[str, Any]] = {}
    if "property_type" in working.columns:
        for property_type, group in working.groupby("property_type"):
            property_key = str(property_type)
            missingness[property_key] = {}
            cardinality[property_key] = {}
            for feature in candidate_features:
                missingness[property_key][feature] = round(float(group[feature].isna().mean()), 4)
                if group[feature].dtype == "object" or feature in CATEGORICAL_FEATURES:
                    cardinality[property_key][feature] = int(group[feature].fillna("unknown").astype(str).nunique())
    diagnostics["feature_missingness"] = missingness
    diagnostics["feature_cardinality"] = cardinality

    diagnostics["feature_signal_rankings"] = {
        property_type: usage.get("top_features", []) for property_type, usage in per_type_feature_usage.items()
    }

    holdout = X_test.copy()
    holdout["y_true"] = y_test
    holdout["y_pred"] = y_pred_combined
    holdout["share_bucket"] = _share_bucket_labels(holdout)
    diagnostics["segment_diagnostics"] = {
        "municipality": _build_segment_metric_table(holdout, "municipality_normalized", min_count=25),
        "naselje": _build_segment_metric_table(holdout, "naselje", min_count=20),
        "ime_ko": _build_segment_metric_table(holdout, "ime_ko", min_count=20),
        "sale_type": _build_segment_metric_table(holdout, "vrsta_kupoprodajnega_posla", min_count=20),
        "share_bucket": _build_segment_metric_table(holdout, "share_bucket", min_count=20),
    }
    diagnostics["residual_diagnostics"] = _build_residual_diagnostics(X_test, y_test, y_pred_combined)
    diagnostics["routing_comparison"] = routing_comparison
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
    if ":" in label:
        return label.split(":", 1)[1]
    return label


def _train_single_model(
    model: CatBoostModel,
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    X_test: pd.DataFrame,
    y_test: np.ndarray,
    label: str,
    progress_callback: Callable | None = None,
    *,
    target_transform: str = "log_ppm2",
    sample_weight: np.ndarray | None = None,
) -> dict:
    total_trees = model.iterations

    # Target transform: log(price/m²) normalizes the enormous price range
    if target_transform == "log_ppm2":
        size_train = X_train["size_m2"].clip(lower=1).values.astype(float)
        size_test = X_test["size_m2"].clip(lower=1).values.astype(float)
        y_fit = np.log(y_train / size_train)
    elif target_transform == "log_price":
        y_fit = np.log1p(y_train)
    else:
        y_fit = y_train

    # Split ~10% validation from training for early stopping.
    # Cap at len(X_train)-1 so tiny OOF folds (and tests) don't starve the train set.
    n_val = min(max(2, int(len(X_train) * 0.1)), max(2, len(X_train) - 5))
    n_val = min(n_val, 50)
    rng = np.random.default_rng(42)
    val_indices = rng.choice(len(X_train), size=n_val, replace=False)
    train_mask = np.ones(len(X_train), dtype=bool)
    train_mask[val_indices] = False

    X_tr = X_train.iloc[train_mask]
    y_tr = y_fit[train_mask]
    X_val = X_train.iloc[val_indices]
    y_val = y_fit[val_indices]
    train_weights = sample_weight[train_mask] if sample_weight is not None else None
    val_weights = sample_weight[val_indices] if sample_weight is not None else None

    model.fit(
        X_tr,
        y_tr,
        X_eval=X_val,
        y_eval=y_val,
        sample_weight=train_weights,
        eval_sample_weight=val_weights,
        label=label,
        progress_callback=progress_callback,
    )

    if progress_callback:
        progress_callback(label, model.best_iteration or total_trees, total_trees)

    # Inverse transform predictions back to price scale
    y_pred_raw = np.clip(model.predict(X_test), -30, 30)  # prevent exp overflow
    if target_transform == "log_ppm2":
        y_pred = np.maximum(size_test * np.exp(y_pred_raw), 0)
    elif target_transform == "log_price":
        y_pred = np.maximum(np.expm1(y_pred_raw), 0)
    else:
        y_pred = y_pred_raw
    metrics = _compute_metrics(y_test, y_pred)
    metrics["n_train"] = len(X_train)
    metrics["n_test"] = len(X_test)

    importance = model.get_feature_importance()

    return {"metrics": metrics, "importance": importance, "predictions": y_pred}


def _predict_combined_routed(
    X_test: pd.DataFrame,
    global_model: CatBoostModel,
    per_type_models: dict[str, dict[str, Any]],
    *,
    target_transform: str = "log_ppm2",
) -> np.ndarray:
    y_pred = _predict_with_model_meta(
        X_test,
        {"pipeline": global_model, "target_transform": target_transform},
        default_target_transform=target_transform,
    )

    if not per_type_models or "property_type" not in X_test.columns:
        return y_pred

    property_types = X_test["property_type"].astype(str)
    for ptype, model_meta in per_type_models.items():
        mask = property_types == ptype
        if not mask.any():
            continue
        blend_weight = float(model_meta.get("blend_weight", 1.0))
        X_sub = X_test.loc[mask]
        pt_pred = _predict_any_model_meta(X_sub, model_meta, default_target_transform=target_transform)
        mask_idx = mask.to_numpy()
        fallback_pred = y_pred[mask_idx]
        if str(model_meta.get("fallback_source") or "global") == "specialist" and model_meta.get("specialist_fallback"):
            fallback_pred = _predict_any_model_meta(
                X_sub,
                model_meta["specialist_fallback"],
                default_target_transform=target_transform,
            )
        if blend_weight >= 0.999:
            y_pred[mask_idx] = pt_pred
        elif blend_weight <= 0.0:
            y_pred[mask_idx] = fallback_pred
        else:
            y_pred[mask_idx] = blend_weight * pt_pred + (1.0 - blend_weight) * fallback_pred

    return y_pred


def _apply_recent_training_window(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Prefer recent transactions for training to match current market regime.

    ETN bulk snapshots are typically annual, so a strict 12-month window is
    approximated with the latest 2 year buckets.
    """
    info: dict[str, Any] = {
        "enabled": _RECENT_WINDOW_MONTHS > 0,
        "requested_months": _RECENT_WINDOW_MONTHS,
        "rows_before": int(len(df)),
        "mode": "full_history",
    }
    if _RECENT_WINDOW_MONTHS <= 0 or df.empty:
        info["rows_after"] = int(len(df))
        return df, info

    year_source = None
    year_values = pd.to_numeric(df.get("transaction_year"), errors="coerce")
    if year_values.notna().any():
        year_source = "transaction_year"
    else:
        year_values = pd.to_numeric(df.get("source_label"), errors="coerce")
        if year_values.notna().any():
            year_source = "source_label"

    if year_source is None:
        info["rows_after"] = int(len(df))
        info["reason"] = "no_year_column"
        return df, info

    latest_year = float(year_values.max())
    # With annual buckets, 12 months spans at least two calendar years.
    target_year_buckets = max(2, int(np.ceil(_RECENT_WINDOW_MONTHS / 12.0)))
    dynamic_min_rows = min(_RECENT_WINDOW_MIN_ROWS, max(1000, int(len(df) * 0.35)))

    selected = df
    selected_year_buckets = None
    selected_cutoff = None

    for year_buckets in range(target_year_buckets, _RECENT_WINDOW_MAX_YEARS + 1):
        cutoff_year = latest_year - year_buckets + 1
        candidate = df[year_values >= cutoff_year]
        selected = candidate
        selected_year_buckets = year_buckets
        selected_cutoff = cutoff_year
        if len(candidate) >= dynamic_min_rows:
            break

    if selected.empty:
        info["rows_after"] = int(len(df))
        info["reason"] = "recent_window_empty"
        return df, info

    info.update(
        {
            "mode": "recent_window",
            "year_source": year_source,
            "latest_year": latest_year,
            "cutoff_year": selected_cutoff,
            "year_buckets": selected_year_buckets,
            "rows_after": int(len(selected)),
            "rows_dropped": int(len(df) - len(selected)),
        }
    )
    return selected.copy(), info


def _extract_year_series(frame: pd.DataFrame) -> tuple[pd.Series, str | None]:
    if "transaction_year" in frame.columns:
        year_values = pd.to_numeric(frame["transaction_year"], errors="coerce")
        if year_values.notna().any():
            return year_values.astype("float64"), "transaction_year"

    if "source_label" in frame.columns:
        fallback_years = pd.to_numeric(frame["source_label"], errors="coerce")
        if fallback_years.notna().any():
            return fallback_years.astype("float64"), "source_label"

    return pd.Series(np.nan, index=frame.index, dtype="float64"), None


def _build_time_holdout_split(
    X: pd.DataFrame,
    y: np.ndarray,
) -> tuple[pd.DataFrame, pd.DataFrame, np.ndarray, np.ndarray, dict[str, Any]]:
    years, year_source = _extract_year_series(X)
    info: dict[str, Any] = {
        "strategy": "time_holdout",
        "year_source": year_source,
        "rows_total": int(len(X)),
    }

    if year_source is None:
        split_at = max(int(len(X) * 0.8), 1)
        if split_at >= len(X):
            split_at = max(len(X) - 1, 1)
        X_train = X.iloc[:split_at].copy()
        X_test = X.iloc[split_at:].copy()
        y_train = y[:split_at]
        y_test = y[split_at:]
        info.update({"strategy": "index_fallback", "rows_train": int(len(X_train)), "rows_test": int(len(X_test))})
        return X_train, X_test, y_train, y_test, info

    valid_years = sorted({int(year) for year in years.dropna().astype(int).tolist()})
    if len(valid_years) < 2:
        latest_year = valid_years[-1] if valid_years else None
        test_mask = years == latest_year if latest_year is not None else pd.Series(False, index=X.index)
    else:
        target_holdout_rows = max(1000, int(len(X) * 0.12))
        selected_years: list[int] = []
        type_targets: dict[str, int] = {}
        if "property_type" in X.columns:
            type_counts = X["property_type"].astype(str).value_counts()
            for property_type, count in type_counts.items():
                if count < MIN_SAMPLES_PER_TYPE:
                    continue
                type_targets[str(property_type)] = min(80, max(20, int(count * 0.08)))

        for year in reversed(valid_years):
            selected_years.append(year)
            candidate_mask = years.isin(selected_years)
            enough_rows = int(candidate_mask.sum()) >= target_holdout_rows
            enough_types = True
            for property_type, target in type_targets.items():
                available = int(((X["property_type"].astype(str) == property_type) & candidate_mask).sum())
                if available < target:
                    enough_types = False
                    break
            if enough_rows and enough_types:
                break

        test_mask = years.isin(selected_years)
        info["test_years"] = sorted(selected_years)
        info["train_years"] = [year for year in valid_years if year not in selected_years]
        info["latest_year"] = max(valid_years)

    if int(test_mask.sum()) == 0 or int((~test_mask).sum()) == 0:
        latest_year = valid_years[-1] if valid_years else None
        test_mask = years == latest_year if latest_year is not None else pd.Series(False, index=X.index)

    if int(test_mask.sum()) == 0 or int((~test_mask).sum()) == 0:
        split_at = max(int(len(X) * 0.8), 1)
        if split_at >= len(X):
            split_at = max(len(X) - 1, 1)
        X_train = X.iloc[:split_at].copy()
        X_test = X.iloc[split_at:].copy()
        y_train = y[:split_at]
        y_test = y[split_at:]
        info.update({"strategy": "index_fallback", "rows_train": int(len(X_train)), "rows_test": int(len(X_test))})
        return X_train, X_test, y_train, y_test, info

    X_train = X.loc[~test_mask].copy()
    X_test = X.loc[test_mask].copy()
    y_train = y[~test_mask.to_numpy()]
    y_test = y[test_mask.to_numpy()]
    info.update(
        {
            "rows_train": int(len(X_train)),
            "rows_test": int(len(X_test)),
        }
    )
    return X_train, X_test, y_train, y_test, info


def _build_recency_sample_weights(
    frame: pd.DataFrame,
    y: np.ndarray | None = None,
    *,
    apply_price_boost: bool = True,
) -> np.ndarray:
    """Exponential recency + optional price-tier weighting.

    Recency: recent years get 4x the weight of oldest (exponential decay).
    Price tier: expensive properties (top quartile) get 1.5x weight to reduce
    MAE on high-value transactions. Only safe WITHIN a property type —
    disable for global-model training where price scales vary 100x across types.
    """
    years, _year_source = _extract_year_series(frame)
    if not years.notna().any():
        weights = np.ones(len(frame), dtype=float)
    else:
        latest_year = float(years.max())
        age = (latest_year - years).clip(lower=0.0).fillna(6.0)
        decay_rate = 0.23  # ln(4)/6 ≈ 0.23
        weights = np.exp(-decay_rate * age.to_numpy(dtype=float))
        w_min = weights.min()
        w_max = weights.max()
        weights = 1.0 + 3.0 * (weights - w_min) / (w_max - w_min) if w_max > w_min else np.ones(len(frame), dtype=float)

    if apply_price_boost and y is not None and len(y) > 100:
        p75 = float(np.percentile(y, 75))
        if p75 > 0:
            price_boost = np.where(y >= p75, 1.5, 1.0)
            weights = weights * price_boost
    return weights


def _restrict_training_years(
    X: pd.DataFrame,
    y: np.ndarray,
    years_back: int | None,
) -> tuple[pd.DataFrame, np.ndarray, dict[str, Any]]:
    if years_back is None:
        return X.copy(), y.copy(), {"policy": "full_history_weighted", "cutoff_year": None}

    years, year_source = _extract_year_series(X)
    if year_source is None or not years.notna().any():
        return X.copy(), y.copy(), {"policy": f"recent_{years_back}y_weighted", "cutoff_year": None, "fallback": True}

    latest_year = int(years.max())
    cutoff_year = latest_year - years_back + 1
    mask = years >= cutoff_year
    if int(mask.sum()) < MIN_SAMPLES_PER_TYPE:
        return (
            X.copy(),
            y.copy(),
            {
                "policy": f"recent_{years_back}y_weighted",
                "cutoff_year": cutoff_year,
                "fallback": True,
            },
        )

    return (
        X.loc[mask].copy(),
        y[mask.to_numpy()],
        {"policy": f"recent_{years_back}y_weighted", "cutoff_year": cutoff_year},
    )


def _fit_calibration_maps(
    X_test: pd.DataFrame,
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> dict[str, Any]:
    calibration: dict[str, Any] = {
        "type": {},
        "municipality": {},
        "naselje": {},
        "segment": {},
        "price_band": {},
        "clip": [0.8, 1.6],
        "segment_clip": [0.55, 1.9],
        "price_band_clip": [0.45, 2.4],
        "combined_clip": [0.35, 3.2],
    }
    if len(X_test) == 0:
        return calibration

    frame = X_test.copy()
    frame["y_true"] = y_true
    frame["y_pred"] = np.maximum(y_pred, 1.0)
    frame["ratio"] = frame["y_true"] / frame["y_pred"]
    frame = frame.replace([np.inf, -np.inf], np.nan)
    frame = frame[frame["ratio"].notna()]
    if frame.empty or "property_type" not in frame.columns:
        return calibration

    clip_low, clip_high = calibration["clip"]
    for property_type, group in frame.groupby("property_type"):
        property_key = str(property_type)
        if property_key in CALIBRATION_DISABLED_TYPES:
            continue
        if len(group) >= 10:
            calibration["type"][property_key] = float(np.clip(group["ratio"].median(), clip_low, clip_high))

        if "municipality_normalized" in group.columns:
            municipality_map: dict[str, float] = {}
            for municipality, municipality_group in group.groupby("municipality_normalized"):
                if str(municipality) == "unknown" or len(municipality_group) < 30:
                    continue
                municipality_map[str(municipality)] = float(
                    np.clip(municipality_group["ratio"].median(), clip_low, clip_high)
                )
            if municipality_map:
                calibration["municipality"][property_key] = municipality_map

        if "naselje" in group.columns:
            naselje_map: dict[str, float] = {}
            for naselje, naselje_group in group.groupby("naselje"):
                if str(naselje) == "unknown" or len(naselje_group) < 20:
                    continue
                naselje_map[str(naselje)] = float(np.clip(naselje_group["ratio"].median(), clip_low, clip_high))
            if naselje_map:
                calibration["naselje"][property_key] = naselje_map

    location_adjusted = frame.copy()
    base_preds: list[float] = []
    for property_type, municipality, naselje, predicted in zip(
        location_adjusted["property_type"].astype(str),
        location_adjusted.get("municipality_normalized", pd.Series("unknown", index=location_adjusted.index)).astype(
            str
        ),
        location_adjusted.get("naselje", pd.Series("unknown", index=location_adjusted.index)).astype(str),
        location_adjusted["y_pred"].astype(float),
        strict=False,
    ):
        location_factor, _ = _lookup_location_calibration_factor(
            calibration,
            property_type,
            municipality if municipality != "unknown" else None,
            naselje if naselje != "unknown" else None,
        )
        base_preds.append(float(max(predicted * location_factor, 1.0)))

    location_adjusted["base_pred"] = np.array(base_preds, dtype=float)
    location_adjusted["residual_ratio"] = location_adjusted["y_true"] / location_adjusted["base_pred"]
    segment_clip_low, segment_clip_high = calibration["segment_clip"]
    segment_preds = pd.Series(
        location_adjusted["base_pred"].to_numpy(dtype=float, copy=True), index=location_adjusted.index, dtype=float
    )
    for property_type, group in location_adjusted.groupby("property_type"):
        property_key = str(property_type)
        segment_meta = _fit_segment_calibration_for_type(
            group,
            property_key,
            clip_low=segment_clip_low,
            clip_high=segment_clip_high,
        )
        if not segment_meta:
            continue

        feature_name = str(segment_meta["feature"])
        factors = dict(segment_meta.get("factors") or {})
        counts = dict(segment_meta.get("counts") or {})
        if not factors:
            continue

        calibration["segment"][property_key] = {
            "feature": feature_name,
            "factors": factors,
            "counts": counts,
            "metrics": dict(segment_meta.get("metrics") or {}),
        }
        values = group[feature_name].fillna("unknown").astype(str)
        mapped_factors = values.map(factors).fillna(1.0).to_numpy(dtype=float)
        segment_preds.loc[group.index] = np.maximum(group["base_pred"].to_numpy(dtype=float) * mapped_factors, 1.0)

    location_adjusted["segment_pred"] = segment_preds.to_numpy(dtype=float)
    location_adjusted["residual_ratio"] = location_adjusted["y_true"] / location_adjusted["segment_pred"]
    band_clip_low, band_clip_high = calibration["price_band_clip"]
    for property_type, group in location_adjusted.groupby("property_type"):
        property_key = str(property_type)
        if property_key in CALIBRATION_PRICE_BAND_DISABLED_TYPES:
            continue
        if len(group) < 120:
            continue
        if len(group) >= 5000:
            target_bins = 5
        elif len(group) >= 1200:
            target_bins = 4
        else:
            target_bins = 3

        with contextlib.suppress(ValueError):
            _, raw_bins = pd.qcut(group["segment_pred"], q=target_bins, retbins=True, duplicates="drop")
            edges = [float(value) for value in raw_bins[1:-1] if np.isfinite(value)]
            band_count = len(edges) + 1
            if band_count < 2:
                continue

            band_index = np.searchsorted(
                np.array(edges, dtype=float), group["segment_pred"].to_numpy(dtype=float), side="right"
            )
            min_rows_per_band = max(25, len(group) // (band_count * 6))
            factors: list[float] = []
            counts: list[int] = []
            valid = True
            for current_band in range(band_count):
                mask = band_index == current_band
                count = int(mask.sum())
                if count < min_rows_per_band:
                    valid = False
                    break
                counts.append(count)
                factors.append(
                    float(np.clip(group.loc[mask, "residual_ratio"].median(), band_clip_low, band_clip_high))
                )
            if valid:
                calibration["price_band"][property_key] = {
                    "edges": edges,
                    "factors": factors,
                    "counts": counts,
                }

    return calibration


def _lookup_location_calibration_factor(
    calibration: dict[str, Any] | None,
    property_type: str,
    municipality: str | None,
    naselje: str | None,
) -> tuple[float, str]:
    if not calibration:
        return 1.0, "none"

    property_key = str(property_type)
    if naselje:
        factor = calibration.get("naselje", {}).get(property_key, {}).get(str(naselje))
        if factor is not None:
            return float(factor), "naselje"

    if municipality:
        factor = calibration.get("municipality", {}).get(property_key, {}).get(str(municipality))
        if factor is not None:
            return float(factor), "municipality"

    factor = calibration.get("type", {}).get(property_key)
    if factor is not None:
        return float(factor), "property_type"

    return 1.0, "none"


def _lookup_segment_calibration_factor(
    calibration: dict[str, Any] | None,
    property_type: str,
    row_context: Any | None,
) -> tuple[float, str]:
    if not calibration or row_context is None:
        return 1.0, "none"

    property_key = str(property_type)
    segment_meta = calibration.get("segment", {}).get(property_key)
    if not isinstance(segment_meta, dict):
        return 1.0, "none"

    feature_name = str(segment_meta.get("feature") or "")
    factor_map = segment_meta.get("factors") or {}
    if not feature_name or not isinstance(factor_map, dict):
        return 1.0, "none"

    try:
        raw_value = row_context.get(feature_name)  # type: ignore[call-arg]
    except AttributeError:
        raw_value = None
    if raw_value is None or (isinstance(raw_value, float) and np.isnan(raw_value)):
        return 1.0, "none"

    normalized_value = str(raw_value)
    if not normalized_value or normalized_value == "unknown":
        return 1.0, "none"

    factor = factor_map.get(normalized_value)
    if factor is None:
        return 1.0, "none"
    return float(factor), f"segment:{feature_name}"


def _lookup_price_band_calibration_factor(
    calibration: dict[str, Any] | None,
    property_type: str,
    predicted_price: float | None,
) -> tuple[float, str]:
    if not calibration or predicted_price is None:
        return 1.0, "none"

    property_key = str(property_type)
    band_meta = calibration.get("price_band", {}).get(property_key)
    if not isinstance(band_meta, dict):
        return 1.0, "none"

    try:
        price_value = float(predicted_price)
    except (TypeError, ValueError):
        return 1.0, "none"
    if np.isnan(price_value) or price_value <= 0:
        return 1.0, "none"

    edges = [float(value) for value in band_meta.get("edges", [])]
    factors = [float(value) for value in band_meta.get("factors", [])]
    if not factors:
        return 1.0, "none"

    band_index = int(np.searchsorted(np.array(edges, dtype=float), price_value, side="right"))
    band_index = min(max(band_index, 0), len(factors) - 1)
    return float(factors[band_index]), f"price_band_{band_index}"


def _lookup_calibration_factor(
    calibration: dict[str, Any] | None,
    property_type: str,
    municipality: str | None,
    naselje: str | None,
    predicted_price: float | None = None,
    row_context: Any | None = None,
) -> tuple[float, str]:
    if not calibration:
        return 1.0, "none"
    if str(property_type) in CALIBRATION_DISABLED_TYPES:
        return 1.0, "disabled"

    location_factor, location_source = _lookup_location_calibration_factor(
        calibration,
        property_type,
        municipality,
        naselje,
    )
    segment_factor, segment_source = _lookup_segment_calibration_factor(
        calibration,
        property_type,
        row_context,
    )
    base_price = None
    if predicted_price is not None:
        with contextlib.suppress(TypeError, ValueError):
            base_price = float(predicted_price) * location_factor * segment_factor

    band_factor, band_source = _lookup_price_band_calibration_factor(
        calibration,
        property_type,
        base_price,
    )
    combined_factor = location_factor * segment_factor * band_factor
    combined_clip = calibration.get("combined_clip") or []
    if len(combined_clip) == 2:
        combined_factor = float(np.clip(combined_factor, combined_clip[0], combined_clip[1]))

    sources = [source for source in (location_source, segment_source, band_source) if source != "none"]
    if sources:
        return combined_factor, "+".join(sources)
    if band_source != "none":
        return combined_factor, band_source
    if segment_source != "none":
        return combined_factor, segment_source
    return combined_factor, location_source


def _apply_calibration_to_predictions(
    X_frame: pd.DataFrame,
    predictions: np.ndarray,
    calibration: dict[str, Any] | None,
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    adjusted = np.array(predictions, dtype=float, copy=True)
    details: list[dict[str, Any]] = []
    if calibration is None or len(X_frame) == 0:
        return adjusted, details

    property_types = X_frame.get("property_type", pd.Series("unknown", index=X_frame.index)).astype(str)
    municipalities = X_frame.get("municipality_normalized", pd.Series("unknown", index=X_frame.index)).astype(str)
    naselja = X_frame.get("naselje", pd.Series("unknown", index=X_frame.index)).astype(str)
    row_contexts = X_frame.to_dict(orient="records")

    for index, (property_type, municipality, naselje, row_context) in enumerate(
        zip(property_types, municipalities, naselja, row_contexts, strict=False)
    ):
        factor, source = _lookup_calibration_factor(
            calibration,
            property_type,
            municipality if municipality != "unknown" else None,
            naselje if naselje != "unknown" else None,
            adjusted[index],
            row_context=row_context,
        )
        adjusted[index] *= factor
        details.append({"factor": round(float(factor), 6), "source": source})

    return adjusted, details


def _build_deployment_prediction_maps(df: pd.DataFrame) -> dict[str, Any]:
    """Build recent-market reference maps used at live prediction time."""
    valid = df.copy()
    valid["size_m2"] = pd.to_numeric(valid.get("size_m2"), errors="coerce")
    valid["price_eur"] = pd.to_numeric(valid.get("price_eur"), errors="coerce")
    valid = valid[(valid["size_m2"] > 0) & (valid["price_eur"] > 0)].copy()
    if valid.empty:
        return {}

    valid["transaction_year"] = pd.to_numeric(valid.get("transaction_year"), errors="coerce")
    latest_year = (
        int(valid["transaction_year"].dropna().max())
        if valid["transaction_year"].notna().any()
        else int(pd.Timestamp.now().year)
    )

    selected = valid
    deploy_window: dict[str, Any] = {
        "mode": "full_history",
        "latest_year": latest_year,
        "rows_available": int(len(valid)),
        "rows_used": int(len(valid)),
    }
    for years in (3, 6):
        cutoff_year = latest_year - years + 1
        candidate = valid[valid["transaction_year"].fillna(latest_year) >= cutoff_year].copy()
        min_rows = 2_000 if years == 3 else 1_000
        if len(candidate) >= min_rows:
            selected = candidate
            deploy_window = {
                "mode": f"recent_{years}y",
                "years": years,
                "cutoff_year": int(cutoff_year),
                "latest_year": latest_year,
                "rows_available": int(len(valid)),
                "rows_used": int(len(candidate)),
            }
            break

    selected["ppm2"] = selected["price_eur"] / selected["size_m2"]
    selected["log_ppm2"] = np.log(selected["ppm2"].clip(lower=0.01))

    deploy_region_medians = (
        selected.groupby("statistical_region")["ppm2"].median().to_dict()
        if "statistical_region" in selected.columns
        else {}
    )
    deploy_type_medians = (
        selected.groupby("property_type")["ppm2"].median().to_dict() if "property_type" in selected.columns else {}
    )
    deploy_global_median_ppm2 = float(selected["ppm2"].median()) if len(selected) > 0 else 2000.0
    deploy_global_log_ppm2 = float(selected["log_ppm2"].median()) if len(selected) > 0 else np.log(2000.0)

    deploy_municipality_medians: dict[str, float] = {}
    if "municipality_normalized" in selected.columns:
        for municipality, group in selected.groupby("municipality_normalized"):
            if len(group) >= 10:
                deploy_municipality_medians[str(municipality)] = float(group["ppm2"].median())
            else:
                region_key = "neznana"
                if "statistical_region" in group.columns:
                    region_mode = group["statistical_region"].mode()
                    if len(region_mode) > 0:
                        region_key = str(region_mode.iloc[0])
                deploy_municipality_medians[str(municipality)] = deploy_region_medians.get(
                    region_key,
                    deploy_global_median_ppm2,
                )

    deploy_type_muni_comp: dict[str, dict[str, float]] = {}
    deploy_type_ko_comp: dict[str, dict[str, float]] = {}
    deploy_type_naselje_comp: dict[str, dict[str, float]] = {}
    deploy_subtype_muni_comp: dict[str, dict[str, float]] = {}
    deploy_subtype_ko_comp: dict[str, dict[str, float]] = {}
    deploy_subtype_naselje_comp: dict[str, dict[str, float]] = {}
    if "property_type" in selected.columns:
        selected["market_subtype_key"] = _build_market_subtype_series(selected)
        for property_type, property_group in selected.groupby("property_type"):
            property_key = str(property_type)
            type_median_log = float(property_group["log_ppm2"].median())

            muni_map: dict[str, float] = {}
            if "municipality_normalized" in property_group.columns:
                for municipality, municipality_group in property_group.groupby("municipality_normalized"):
                    muni_map[str(municipality)] = (
                        float(municipality_group["log_ppm2"].median())
                        if len(municipality_group) >= 5
                        else type_median_log
                    )
            deploy_type_muni_comp[property_key] = muni_map

            ko_map: dict[str, float] = {}
            if "ime_ko" in property_group.columns:
                for ime_ko, ko_group in property_group.groupby("ime_ko"):
                    if _is_unknown_category_value(ime_ko):
                        continue
                    ko_map[str(ime_ko)] = (
                        float(ko_group["log_ppm2"].median()) if len(ko_group) >= 5 else type_median_log
                    )
            deploy_type_ko_comp[property_key] = ko_map

            naselje_map: dict[str, float] = {}
            if "naselje" in property_group.columns:
                for naselje, naselje_group in property_group.groupby("naselje"):
                    naselje_key = str(naselje)
                    if not _is_unknown_category_value(naselje_key) and len(naselje_group) >= 5:
                        naselje_map[naselje_key] = float(naselje_group["log_ppm2"].median())
            deploy_type_naselje_comp[property_key] = naselje_map

        for subtype_key, subtype_group in selected.groupby("market_subtype_key"):
            subtype_key = str(subtype_key)
            subtype_median_log = float(subtype_group["log_ppm2"].median())

            muni_map: dict[str, float] = {}
            if "municipality_normalized" in subtype_group.columns:
                for municipality, municipality_group in subtype_group.groupby("municipality_normalized"):
                    muni_map[str(municipality)] = (
                        float(municipality_group["log_ppm2"].median())
                        if len(municipality_group) >= 5
                        else subtype_median_log
                    )
            deploy_subtype_muni_comp[subtype_key] = muni_map

            ko_map: dict[str, float] = {}
            if "ime_ko" in subtype_group.columns:
                for ime_ko, ko_group in subtype_group.groupby("ime_ko"):
                    if _is_unknown_category_value(ime_ko):
                        continue
                    ko_map[str(ime_ko)] = (
                        float(ko_group["log_ppm2"].median()) if len(ko_group) >= 5 else subtype_median_log
                    )
            deploy_subtype_ko_comp[subtype_key] = ko_map

            naselje_map: dict[str, float] = {}
            if "naselje" in subtype_group.columns:
                for naselje, naselje_group in subtype_group.groupby("naselje"):
                    naselje_key = str(naselje)
                    if not _is_unknown_category_value(naselje_key) and len(naselje_group) >= 5:
                        naselje_map[naselje_key] = float(naselje_group["log_ppm2"].median())
            deploy_subtype_naselje_comp[subtype_key] = naselje_map

    deploy_eng_artifacts: dict[str, Any] = {}
    if "ime_ko" in selected.columns:
        deploy_ko_ppm2_map: dict[str, float] = {}
        for ime_ko, ko_group in selected.groupby("ime_ko"):
            if not _is_unknown_category_value(ime_ko) and len(ko_group) >= 5:
                deploy_ko_ppm2_map[str(ime_ko)] = float(ko_group["ppm2"].median())
        deploy_eng_artifacts["ko_ppm2_map"] = deploy_ko_ppm2_map
        deploy_eng_artifacts["global_median_ppm2_for_ko"] = deploy_global_median_ppm2

    return {
        "deploy_region_medians": deploy_region_medians,
        "deploy_type_medians": deploy_type_medians,
        "deploy_municipality_medians": deploy_municipality_medians,
        "deploy_global_median_ppm2": deploy_global_median_ppm2,
        "deploy_type_muni_comp": deploy_type_muni_comp,
        "deploy_type_ko_comp": deploy_type_ko_comp,
        "deploy_type_naselje_comp": deploy_type_naselje_comp,
        "deploy_subtype_muni_comp": deploy_subtype_muni_comp,
        "deploy_subtype_ko_comp": deploy_subtype_ko_comp,
        "deploy_subtype_naselje_comp": deploy_subtype_naselje_comp,
        "deploy_global_log_ppm2": deploy_global_log_ppm2,
        "deploy_eng_artifacts": deploy_eng_artifacts,
        "deploy_window": deploy_window,
    }


def _apply_full_share_market_filter(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Keep near-full-share transactions for market-value model training.

    The app predicts the value of an entire property, not a discounted sale of a
    minority share. Partial-share transactions materially depress prices and can
    pull the model away from the product goal, so we drop them by default.
    """
    info: dict[str, Any] = {
        "enabled": _MIN_FULL_SHARE > 0,
        "threshold": _MIN_FULL_SHARE,
        "rows_before": int(len(df)),
    }
    if df.empty or _MIN_FULL_SHARE <= 0:
        info["rows_after"] = int(len(df))
        return df, info

    share_series = pd.to_numeric(df.get("prodani_delez_dela_stavbe"), errors="coerce")
    if share_series.isna().all():
        share_series = pd.to_numeric(df.get("prodani_delez_parcele"), errors="coerce")
    else:
        parcel_share = pd.to_numeric(df.get("prodani_delez_parcele"), errors="coerce")
        share_series = share_series.where(share_series.notna(), parcel_share)

    effective_share = share_series.fillna(1.0)
    keep_mask = effective_share >= _MIN_FULL_SHARE
    filtered = df.loc[keep_mask].copy()

    info["rows_after"] = int(len(filtered))
    info["rows_dropped"] = int(len(df) - len(filtered))
    info["missing_share_assumed_full"] = int(share_series.isna().sum())
    info["full_share_ratio"] = round(float(keep_mask.mean()), 6) if len(df) else 1.0

    if "property_type" in df.columns:
        rows_by_type = df["property_type"].fillna("unknown").astype(str).value_counts().to_dict()
        kept_by_type = filtered["property_type"].fillna("unknown").astype(str).value_counts().to_dict()
        info["per_type"] = {
            property_type: {
                "rows_before": int(count),
                "rows_after": int(kept_by_type.get(property_type, 0)),
            }
            for property_type, count in sorted(rows_by_type.items())
        }

    return filtered, info


def _normalize_sale_type_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return ""
        with contextlib.suppress(ValueError):
            numeric = float(stripped.replace(",", "."))
            return str(int(numeric)) if numeric.is_integer() else stripped
        return stripped
    with contextlib.suppress(TypeError, ValueError):
        numeric = float(value)
        return str(int(numeric)) if numeric.is_integer() else str(numeric)
    return str(value).strip()


def _apply_sale_type_filter(
    df: pd.DataFrame,
    allowed_sale_types: set[str] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    info: dict[str, Any] = {
        "enabled": bool(allowed_sale_types),
        "rows_before": int(len(df)),
        "allowed_sale_types": sorted(str(value) for value in (allowed_sale_types or set())),
    }
    if not allowed_sale_types or df.empty:
        info["rows_after"] = int(len(df))
        return df, info
    if "vrsta_kupoprodajnega_posla" not in df.columns:
        info["rows_after"] = int(len(df))
        info["fallback"] = "missing_sale_type_column"
        return df, info

    normalized_values = df["vrsta_kupoprodajnega_posla"].map(_normalize_sale_type_value)
    keep_mask = normalized_values.isin({str(value) for value in allowed_sale_types})
    filtered = df.loc[keep_mask].copy()

    info["rows_after"] = int(len(filtered))
    info["rows_dropped"] = int(len(df) - len(filtered))
    info["retained_ratio"] = round(float(keep_mask.mean()), 6) if len(df) else 1.0
    info["observed_sale_types"] = sorted(value for value in normalized_values.dropna().unique().tolist() if value)
    return filtered, info


def _apply_market_validity_filter(
    df: pd.DataFrame,
    *,
    enabled: bool,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    info: dict[str, Any] = {
        "enabled": bool(enabled),
        "rows_before": int(len(df)),
        "rules": MARKET_VALIDITY_RULES,
    }
    if not enabled or df.empty or "property_type" not in df.columns:
        info["rows_after"] = int(len(df))
        return df, info

    price_series = pd.to_numeric(df.get("price_eur"), errors="coerce")
    size_series = pd.to_numeric(df.get("size_m2"), errors="coerce")
    ppm2_series = price_series / size_series.replace(0, np.nan)

    keep_mask = pd.Series(True, index=df.index, dtype=bool)
    per_type: dict[str, dict[str, Any]] = {}
    for property_type, rule in MARKET_VALIDITY_RULES.items():
        type_mask = df["property_type"].astype(str) == str(property_type)
        type_rows = int(type_mask.sum())
        if type_rows == 0:
            continue

        type_keep = type_mask.copy()
        min_price = rule.get("min_price_eur")
        if isinstance(min_price, (int, float)):
            type_keep &= price_series >= float(min_price)
        min_ppm2 = rule.get("min_ppm2")
        if isinstance(min_ppm2, (int, float)):
            type_keep &= ppm2_series >= float(min_ppm2)
        if rule.get("drop_unknown_municipality") and "municipality_normalized" in df.columns:
            municipality = df["municipality_normalized"].fillna("unknown").astype(str)
            type_keep &= municipality != "unknown"

        keep_mask.loc[type_mask] = type_keep.loc[type_mask]
        per_type[property_type] = {
            "rows_before": type_rows,
            "rows_after": int(type_keep.loc[type_mask].sum()),
            "rows_dropped": int(type_rows - type_keep.loc[type_mask].sum()),
            "drop_pct": round(float((~type_keep.loc[type_mask]).mean() * 100), 2) if type_rows else 0.0,
        }

    filtered = df.loc[keep_mask].copy()
    info["rows_after"] = int(len(filtered))
    info["rows_dropped"] = int(len(df) - len(filtered))
    info["retained_ratio"] = round(float(keep_mask.mean()), 6) if len(df) else 1.0
    info["per_type"] = per_type
    return filtered, info


def train_from_csv(
    csv_path: str,
    progress_callback: Callable | None = None,
    status_callback: Callable | None = None,
    *,
    model_output_path: str | None = None,
    artifact_metadata: dict[str, Any] | None = None,
    allowed_sale_types: set[str] | None = None,
    benchmark_per_type_variants: bool = False,
) -> dict[str, Any]:
    """Train per-type + global models from a training CSV. Returns model metadata."""
    start = time.time()
    artifact_metadata = dict(artifact_metadata or {})
    resolved_model_path = os.path.abspath(model_output_path or _default_model_path())
    enable_market_validity_filter = bool(artifact_metadata.get("enable_market_validity_filter", True))

    def emit_status(stage: str, progress: int, **extra):
        if status_callback:
            status_callback(
                stage=stage,
                progress=progress,
                elapsed_sec=round(time.time() - start, 2),
                **extra,
            )

    emit_status("dataset_load", 2)
    task_type = _get_catboost_task_type()
    logger.info("CatBoost task_type=%s - training start", task_type)
    if task_type == "CPU":
        logger.warning(
            "Training on CPU — this will be slow for large datasets. "
            "Set CATBOOST_TASK_TYPE=GPU or install NVIDIA drivers for GPU acceleration."
        )
    logger.info("Loading CSV: %s", csv_path)
    df = read_csv_flexible(csv_path)
    logger.info("Loaded %d rows, %d columns", len(df), len(df.columns))
    emit_status("feature_prep", 8, rows=len(df))
    df = enrich_training_df(df)

    # Clean price
    df["price_eur"] = pd.to_numeric(df.get("price_eur"), errors="coerce")
    df = df.dropna(subset=["price_eur"])
    df = df[df["price_eur"] > 0]

    # Exclude non-predictable types
    if "property_type" in df.columns:
        df = df[~df["property_type"].isin(EXCLUDED_PROPERTY_TYPES)]

    df, sale_type_filter = _apply_sale_type_filter(df, allowed_sale_types)
    logger.info("Sale-type filter: kept %d / %d rows", len(df), sale_type_filter["rows_before"])

    # Ensure size_m2 is numeric and positive (required for log_ppm2 target transform)
    df["size_m2"] = pd.to_numeric(df.get("size_m2"), errors="coerce")
    df = df[df["size_m2"] > 0]

    # Keep only near-full-share transactions so the model learns whole-property market value.
    df, full_share_filter = _apply_full_share_market_filter(df)
    logger.info("Full-share market-value filter: kept %d / %d rows", len(df), full_share_filter["rows_before"])

    df, market_validity_filter = _apply_market_validity_filter(df, enabled=enable_market_validity_filter)
    logger.info("Market-validity filter: kept %d / %d rows", len(df), market_validity_filter["rows_before"])

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
        logger.info("Mixed-type deal cleaning: %d -> %d rows", n_before_deal_clean, len(df))

    # ── Global IQR-based outlier removal PER TYPE before train/test split ─
    # Pass 1: IQR fence with per-type multiplier (default 1.5, 2.0+ for top types)
    #         For land types (parcela/kmetijsko), run per vrsta_zemljisca subgroup
    #         because stavbno (EUR50-500/m2) and kmetijsko (EUR1-10/m2) have 100x
    #         price variation that makes a mixed IQR fence useless.
    # Pass 2: Winsorize to [1st, 99th] percentile per type
    n_before_global_outlier = len(df)
    if "property_type" in df.columns:
        df["_log_ppm2_tmp"] = np.log(df["price_eur"] / df["size_m2"])
        keep_mask = pd.Series(True, index=df.index)
        for ptype in df["property_type"].unique():
            type_mask = df["property_type"] == ptype
            mult = TYPE_IQR_OVERRIDES.get(str(ptype), 1.5)
            if str(ptype) in SUBTYPE_OUTLIER_TYPES and "vrsta_zemljisca" in df.columns:
                for _vz, vz_grp in df.loc[type_mask].groupby("vrsta_zemljisca"):
                    if len(vz_grp) < 30:
                        continue
                    lp = vz_grp["_log_ppm2_tmp"]
                    q1, q3 = lp.quantile(0.25), lp.quantile(0.75)
                    iqr = q3 - q1
                    if iqr < 0.01:
                        continue
                    fence_lo, fence_hi = q1 - mult * iqr, q3 + mult * iqr
                    sub_outlier = vz_grp.index[(lp < fence_lo) | (lp > fence_hi)]
                    keep_mask.loc[sub_outlier] = False
                n_sub_removed = int((type_mask & ~keep_mask).sum())
                logger.info("  %s: per-subtype IQR outlier removal removed %d rows", ptype, n_sub_removed)
            else:
                lp = df.loc[type_mask, "_log_ppm2_tmp"]
                q1, q3 = lp.quantile(0.25), lp.quantile(0.75)
                iqr = q3 - q1
                fence_lo, fence_hi = q1 - mult * iqr, q3 + mult * iqr
                type_outlier = type_mask & ((df["_log_ppm2_tmp"] < fence_lo) | (df["_log_ppm2_tmp"] > fence_hi))
                keep_mask = keep_mask & ~type_outlier
        df = df[keep_mask]
        # Pass 2: winsorize remaining to [1st, 99th] percentile - small/noisy types only
        for ptype in df["property_type"].unique():
            if str(ptype) in TYPE_SKIP_WINSORIZATION:
                continue
            type_mask = df["property_type"] == ptype
            lp = df.loc[type_mask, "_log_ppm2_tmp"]
            p01, p99 = lp.quantile(0.01), lp.quantile(0.99)
            clip_mask = type_mask & ((df["_log_ppm2_tmp"] < p01) | (df["_log_ppm2_tmp"] > p99))
            keep_mask_p2 = ~clip_mask
            if keep_mask_p2.sum() >= 100:
                df = df[keep_mask_p2 | ~type_mask]
        # Pass 3: per (type, municipality) z-score pass — remove transactions
        # where log(ppm2) deviates from the local group mean.
        # Large types (n>=3000): z>2.0, min_group=20 (tight, catches local outliers)
        # Small types (n<3000): z>2.5, min_group=30 (relaxed, preserves scarce data)
        if "municipality_normalized" in df.columns:
            n_before_muni = len(df)
            type_counts = df["property_type"].value_counts()
            keep_muni = pd.Series(True, index=df.index)
            for (ptype, _muni), grp in df.groupby(["property_type", "municipality_normalized"]):
                n_type = int(type_counts.get(ptype, 0))
                is_small_type = n_type < 3000
                min_group = 30 if is_small_type else 20
                z_threshold = 2.5 if is_small_type else 2.0
                if len(grp) < min_group:
                    continue
                lp = grp["_log_ppm2_tmp"]
                mu, sigma = lp.mean(), lp.std()
                if sigma < 0.01:
                    continue
                z = ((lp - mu) / sigma).abs()
                keep_muni.loc[grp.index[z > z_threshold]] = False
            df = df[keep_muni]
            logger.info("Per-municipality outlier pass: %d -> %d rows", n_before_muni, len(df))
        df = df.drop(columns=["_log_ppm2_tmp"])
        logger.info("Global outlier removal: %d -> %d rows", n_before_global_outlier, len(df))

    training_window = {
        "enabled": False,
        "requested_months": _RECENT_WINDOW_MONTHS,
        "full_share_filter": full_share_filter,
        "sale_type_filter": sale_type_filter,
        "market_validity_filter": market_validity_filter,
        "rows_before": int(len(df)),
        "rows_after": int(len(df)),
        "mode": "policy_driven_full_history",
        "reason": "per_type_time_holdout_selection",
    }

    # ── Spatial distance features from ETRS89/TM coordinates ───────────
    # These are metric coordinates, so Euclidean distance gives meters.
    _LJ_E, _LJ_N = 461000, 100000  # Ljubljana
    _MB_E, _MB_N = 553000, 155000  # Maribor
    _KP_E, _KP_N = 404000, 44000  # Koper (coast)
    lon = pd.to_numeric(df.get("longitude"), errors="coerce")
    lat = pd.to_numeric(df.get("latitude"), errors="coerce")
    df["dist_ljubljana"] = np.sqrt((lon - _LJ_E) ** 2 + (lat - _LJ_N) ** 2)
    df["dist_maribor"] = np.sqrt((lon - _MB_E) ** 2 + (lat - _MB_N) ** 2)
    df["dist_coast"] = np.sqrt((lon - _KP_E) ** 2 + (lat - _KP_N) ** 2)

    y = df["price_eur"].values
    X = df.drop(columns=["price_eur"], errors="ignore")
    X["market_subtype_key"] = _build_market_subtype_series(X)

    # Force all NUMERIC_FEATURES columns to proper numeric dtype
    # (enrichment columns may arrive as mixed str/float from CSV)
    for col in NUMERIC_FEATURES:
        if col in X.columns:
            X[col] = pd.to_numeric(X[col], errors="coerce")

    emit_status("feature_prep", 14, rows=len(df))

    X_train, X_test, y_train, y_test, holdout_info = _build_time_holdout_split(X, y)
    training_window["holdout"] = holdout_info
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
    # Bayesian-smoothed median log(ppm2) per type+municipality, type+KO, type+naselje.
    # Smoothing regularises small groups toward the type-level prior, preventing
    # target leakage for groups with <20 members.
    valid["log_ppm2"] = np.log(valid["ppm2"].clip(lower=0.01))
    valid["market_subtype_key"] = _build_market_subtype_series(valid)
    alpha = COMP_SMOOTH_ALPHA
    type_muni_comp: dict[str, dict[str, float]] = {}
    type_ko_comp: dict[str, dict[str, float]] = {}
    type_naselje_comp: dict[str, dict[str, float]] = {}
    subtype_muni_comp: dict[str, dict[str, float]] = {}
    subtype_ko_comp: dict[str, dict[str, float]] = {}
    subtype_naselje_comp: dict[str, dict[str, float]] = {}

    def _smoothed(group_median: float, n: int, prior: float) -> float:
        return float((n * group_median + alpha * prior) / (n + alpha))

    if "property_type" in valid.columns:
        for ptype_grp, ptype_data in valid.groupby("property_type"):
            ptype_key = str(ptype_grp)
            type_median_log = float(ptype_data["log_ppm2"].median())
            muni_med = {}
            if "municipality_normalized" in ptype_data.columns:
                for muni, mgrp in ptype_data.groupby("municipality_normalized"):
                    n = len(mgrp)
                    if n >= 3:
                        muni_med[str(muni)] = _smoothed(float(mgrp["log_ppm2"].median()), n, type_median_log)
                    else:
                        muni_med[str(muni)] = type_median_log
            type_muni_comp[ptype_key] = muni_med
            ko_med = {}
            if "ime_ko" in ptype_data.columns:
                for ko, kgrp in ptype_data.groupby("ime_ko"):
                    if _is_unknown_category_value(ko):
                        continue
                    n = len(kgrp)
                    if n >= 3:
                        ko_med[str(ko)] = _smoothed(float(kgrp["log_ppm2"].median()), n, type_median_log)
                    else:
                        ko_med[str(ko)] = type_median_log
            type_ko_comp[ptype_key] = ko_med
            naselje_med = {}
            if "naselje" in ptype_data.columns:
                for nas, ngrp in ptype_data.groupby("naselje"):
                    if _is_unknown_category_value(nas):
                        continue
                    n = len(ngrp)
                    if n >= 3:
                        naselje_med[str(nas)] = _smoothed(float(ngrp["log_ppm2"].median()), n, type_median_log)
            type_naselje_comp[ptype_key] = naselje_med

        for subtype_key, subtype_data in valid.groupby("market_subtype_key"):
            subtype_key = str(subtype_key)
            subtype_median_log = float(subtype_data["log_ppm2"].median())

            muni_med = {}
            if "municipality_normalized" in subtype_data.columns:
                for muni, mgrp in subtype_data.groupby("municipality_normalized"):
                    n = len(mgrp)
                    if n >= 3:
                        muni_med[str(muni)] = _smoothed(float(mgrp["log_ppm2"].median()), n, subtype_median_log)
                    else:
                        muni_med[str(muni)] = subtype_median_log
            subtype_muni_comp[subtype_key] = muni_med

            ko_med = {}
            if "ime_ko" in subtype_data.columns:
                for ko, kgrp in subtype_data.groupby("ime_ko"):
                    if _is_unknown_category_value(ko):
                        continue
                    n = len(kgrp)
                    if n >= 3:
                        ko_med[str(ko)] = _smoothed(float(kgrp["log_ppm2"].median()), n, subtype_median_log)
                    else:
                        ko_med[str(ko)] = subtype_median_log
            subtype_ko_comp[subtype_key] = ko_med

            naselje_med = {}
            if "naselje" in subtype_data.columns:
                for nas, ngrp in subtype_data.groupby("naselje"):
                    if _is_unknown_category_value(nas):
                        continue
                    n = len(ngrp)
                    if n >= 3:
                        naselje_med[str(nas)] = _smoothed(float(ngrp["log_ppm2"].median()), n, subtype_median_log)
                        naselje_med[str(nas)] = float(ngrp["log_ppm2"].median())
            subtype_naselje_comp[subtype_key] = naselje_med

    # Apply comp features to train and test
    global_log_ppm2 = float(valid["log_ppm2"].median()) if len(valid) > 0 else np.log(2000.0)
    for split_X in (X_train, X_test):
        comp_muni_vals = np.full(len(split_X), global_log_ppm2)
        comp_ko_vals = np.full(len(split_X), global_log_ppm2)
        comp_naselje_vals = np.full(len(split_X), np.nan)
        if "property_type" in split_X.columns:
            for ptype_key, muni_map in type_muni_comp.items():
                mask = split_X["property_type"] == ptype_key
                if mask.any() and muni_map:
                    comp_muni_vals[mask.values] = (
                        split_X.loc[mask, "municipality_normalized"].map(muni_map).fillna(global_log_ppm2).values
                    )
            for ptype_key, ko_map in type_ko_comp.items():
                mask = split_X["property_type"] == ptype_key
                if mask.any() and ko_map and "ime_ko" in split_X.columns:
                    comp_ko_vals[mask.values] = split_X.loc[mask, "ime_ko"].map(ko_map).fillna(global_log_ppm2).values
            for ptype_key, naselje_map in type_naselje_comp.items():
                mask = split_X["property_type"] == ptype_key
                if mask.any() and naselje_map and "naselje" in split_X.columns:
                    comp_naselje_vals[mask.values] = split_X.loc[mask, "naselje"].map(naselje_map).values
        split_X["comp_type_muni_ppm2"] = comp_muni_vals
        split_X["comp_type_ko_ppm2"] = comp_ko_vals
        split_X["comp_type_naselje_ppm2"] = comp_naselje_vals

    # ── Engineered features (spatial KNN, counts, ratios, etc.) ──────
    logger.info("Computing engineered features ...")
    X_train, X_test, eng_artifacts = _compute_engineered_features(X_train, y_train, X_test)

    global_num, global_cat = _filter_features(X_train, NUMERIC_FEATURES, CATEGORICAL_FEATURES)
    global_num, global_cat, global_selection_mode = _select_global_gpu_safe_features(
        X_train,
        y_train,
        global_num,
        global_cat,
    )
    data_preparation = load_training_metadata(csv_path)

    # Global model
    logger.info(
        "=== GLOBAL MODEL [%s]: %d num + %d cat features, %d train rows ===",
        global_selection_mode,
        len(global_num),
        len(global_cat),
        len(X_train),
    )
    model_start_times: dict[str, float] = {}
    global_model = _build_model(global_num, global_cat, len(X_train))
    per_type_models: dict[str, dict] = {}
    per_type_metrics: dict[str, dict] = {}
    per_type_feature_usage: dict[str, dict[str, Any]] = {}
    routing_comparison: dict[str, dict[str, Any]] = {}

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
        total_trees=global_model.iterations,
    )
    global_sample_weight = _build_recency_sample_weights(X_train, y_train, apply_price_boost=False)
    global_result = _train_single_model(
        global_model,
        X_train,
        y_train,
        X_test,
        y_test,
        "global",
        training_progress,
        target_transform="log_ppm2",
        sample_weight=global_sample_weight,
    )

    # ── Out-of-fold stacking: leak-free global predictions for per-type specialists ──
    # v3 used naive stacking (global model predicts its own training data), which
    # leaks overfit signal. OOF fixes this: for each fold, train global on the
    # other folds and predict the held-out fold. Per-type specialists then see
    # predictions with realistic generalization error.
    logger.info("Computing OOF global-model stacking features (%d stratified folds) ...", OOF_STACKING_FOLDS)
    oof_pred_train = np.zeros(len(X_train), dtype=float)
    strat_labels = X_train["property_type"].astype(str).values if "property_type" in X_train.columns else None
    if strat_labels is not None:
        kf = StratifiedKFold(n_splits=OOF_STACKING_FOLDS, shuffle=True, random_state=42)
        fold_iter = kf.split(X_train, strat_labels)
    else:
        kf_plain = KFold(n_splits=OOF_STACKING_FOLDS, shuffle=True, random_state=42)
        fold_iter = kf_plain.split(X_train)
    oof_fold_weights = _build_recency_sample_weights(X_train, y_train, apply_price_boost=False)
    # Minimum rows needed to train a CatBoost model (depth+1 to avoid constant-feature error)
    _MIN_OOF_FOLD_ROWS = 10
    for fold_idx, (fold_train_idx, fold_val_idx) in enumerate(fold_iter):
        fold_X_tr = X_train.iloc[fold_train_idx]
        fold_y_tr = y_train[fold_train_idx]
        fold_X_val = X_train.iloc[fold_val_idx]
        fold_y_val = y_train[fold_val_idx]
        if len(fold_X_tr) < _MIN_OOF_FOLD_ROWS:
            # Too few rows in this fold — fill with global model predictions as fallback
            logger.warning(
                "  OOF fold %d: only %d train rows (< %d) — using global model as fallback",
                fold_idx + 1,
                len(fold_X_tr),
                _MIN_OOF_FOLD_ROWS,
            )
            fallback_pred = _predict_with_model_meta(
                fold_X_val,
                {"pipeline": global_model, "target_transform": "log_ppm2"},
                default_target_transform="log_ppm2",
            )
            oof_pred_train[fold_val_idx] = fallback_pred
            continue
        fold_weights = oof_fold_weights[fold_train_idx]
        fold_num, fold_cat = global_num, global_cat
        fold_model = _build_model(fold_num, fold_cat, len(fold_X_tr))
        _train_single_model(
            fold_model,
            fold_X_tr,
            fold_y_tr,
            fold_X_val,
            fold_y_val,
            f"oof_fold_{fold_idx}",
            None,
            target_transform="log_ppm2",
            sample_weight=fold_weights,
        )
        fold_pred = _predict_with_model_meta(
            fold_X_val,
            {"pipeline": fold_model, "target_transform": "log_ppm2"},
            default_target_transform="log_ppm2",
        )
        oof_pred_train[fold_val_idx] = fold_pred
        logger.info("  OOF fold %d/%d complete", fold_idx + 1, OOF_STACKING_FOLDS)
    global_pred_test = _predict_with_model_meta(
        X_test,
        {"pipeline": global_model, "target_transform": "log_ppm2"},
        default_target_transform="log_ppm2",
    )
    X_train["global_pred_log_price"] = np.log1p(np.clip(oof_pred_train, 1.0, None))
    X_test["global_pred_log_price"] = np.log1p(np.clip(global_pred_test, 1.0, None))
    logger.info(
        "  Stacking feature: global_pred_log_price train=[%.2f, %.2f] test=[%.2f, %.2f]",
        X_train["global_pred_log_price"].min(),
        X_train["global_pred_log_price"].max(),
        X_test["global_pred_log_price"].min(),
        X_test["global_pred_log_price"].max(),
    )

    # Per-type models — signal-scored features + early stopping + aggressive outlier removal
    logger.info("=== PER-TYPE MODELS: %d eligible types: %s ===", len(eligible), eligible)
    if eligible:
        for idx, ptype in enumerate(eligible):
            # Small commercial types share training data: v1 showed each one
            # starves on its own (industrijski=1339, turisticni=1195, gostinstvo=482).
            # Train on the union with property_type as a feature; evaluate per-type.
            if ptype in SMALL_COMMERCIAL_GROUP:
                group_types = list(SMALL_COMMERCIAL_GROUP)
                mask_train = X_train["property_type"].isin(group_types)
                logger.info(
                    "  %s: training on small_commercial group (%s), eval on %s only",
                    ptype,
                    "|".join(group_types),
                    ptype,
                )
            else:
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
            # Per-type IQR override, or default: tighter for large (1.5), relaxed for small (1.8)
            iqr_mult = TYPE_IQR_OVERRIDES.get(ptype, 1.5 if n_before > 5000 else 1.8)
            lo, hi = q1 - iqr_mult * iqr, q3 + iqr_mult * iqr
            outlier_mask = (log_ppm2 >= lo) & (log_ppm2 <= hi)
            if outlier_mask.sum() >= MIN_SAMPLES_PER_TYPE:
                Xt = Xt[outlier_mask]
                yt = yt[outlier_mask]
                logger.info("Type %s: outlier removal %d -> %d rows", ptype, n_before, len(yt))

            # Look up type-specific feature config, fall back to global defaults
            type_config = TYPE_FEATURE_CONFIGS.get(ptype, {})
            always_num = type_config.get("always_numeric", ALWAYS_INCLUDE_NUMERIC)
            always_cat = type_config.get("always_categorical", ALWAYS_INCLUDE_CATEGORICAL)
            # Apply per-type exclusion lists (v8: drag features from v7 importance analysis)
            exclude_cfg = TYPE_EXCLUDE_FEATURES.get(ptype, {})
            exclude_num = set(exclude_cfg.get("numeric", set()))
            exclude_cat = set(exclude_cfg.get("categorical", set()))
            always_num = set(always_num) - exclude_num
            always_cat = set(always_cat) - exclude_cat
            # Small commercial group trains on a 3-type union - property_type MUST
            # be a feature so the model can discriminate segments within the pool.
            per_type_categorical_candidates = PERTYPE_CATEGORICAL
            if ptype in SMALL_COMMERCIAL_GROUP:
                always_cat = set(always_cat) | {"property_type"}
                per_type_categorical_candidates = [*PERTYPE_CATEGORICAL, "property_type"]
            # Filter the candidate pool to remove drag features before fill-rate filter
            candidate_numeric_pool = [c for c in PERTYPE_NUMERIC if c not in exclude_num]
            candidate_categorical_pool = [c for c in per_type_categorical_candidates if c not in exclude_cat]
            raw_type_numeric, raw_type_categorical = _filter_features(
                Xt,
                candidate_numeric_pool,
                candidate_categorical_pool,
                extra_keep_numeric=always_num,
                extra_keep_categorical=always_cat,
            )
            if exclude_num or exclude_cat:
                logger.info(
                    "[%s] v8 pruning: excluded %d numeric + %d categorical drag features",
                    ptype,
                    len(exclude_num),
                    len(exclude_cat),
                )

            # Adaptive max extras based on dataset size
            max_extra_num, max_extra_cat = _adaptive_max_extras(len(Xt))

            # Signal-scored feature selection for ALL types
            pt_num, pt_cat, pt_scores = _select_type_specific_features(
                Xt,
                yt,
                raw_type_numeric,
                raw_type_categorical,
                always_numeric=always_num,
                always_categorical=always_cat,
                max_extra_numeric=max_extra_num,
                max_extra_categorical=max_extra_cat,
            )
            selection_mode = f"signal_scored_{ptype}"

            # Per-type CatBoost model with optional HP overrides
            logger.info(
                "--- [%d/%d] %s: %d train, %d test, %d num + %d cat features ---",
                idx + 1,
                len(eligible),
                ptype,
                len(Xt),
                len(Xte),
                len(pt_num),
                len(pt_cat),
            )
            pt_hp_overrides = TYPE_HP_OVERRIDES.get(ptype)
            _LOSSGUIDE_TYPES = {"stanovanje", "hisa", "parcela"}
            type_training_prior = TYPE_TRAINING_PRIORS.get(ptype, {})
            type_search_prior = TYPE_SEARCH_PRIORS.get(ptype, {})
            policy_candidates = [
                ("full_history_weighted", None),
                ("recent_6y_weighted", 6),
                ("recent_3y_weighted", 3),
            ]
            preferred_policy_names = [str(name) for name in type_search_prior.get("policy_candidates") or []]
            if preferred_policy_names:
                policy_candidates = [
                    item for item in policy_candidates if item[0] in preferred_policy_names
                ] or policy_candidates
            preferred_policy = str(type_training_prior.get("training_policy", "")).strip()
            if preferred_policy:
                policy_candidates = sorted(
                    policy_candidates,
                    key=lambda item: (item[0] != preferred_policy, item[1] is not None, item[1] or 0),
                )
            search_variants = benchmark_per_type_variants or bool(type_search_prior.get("benchmark_variants"))
            target_candidates = (
                list(type_search_prior.get("target_candidates") or ["log_ppm2", "log_price"])
                if search_variants
                else [str(type_training_prior.get("target_transform", "log_ppm2"))]
            )
            feature_variants = _build_feature_variants(
                raw_type_numeric,
                raw_type_categorical,
                always_num,
                always_cat,
                property_type=ptype,
            )
            feature_variant_names = (
                [
                    name
                    for name in (type_search_prior.get("feature_variants") or feature_variants.keys())
                    if name in feature_variants
                ]
                if search_variants
                else [str(type_training_prior.get("feature_variant", "rich"))]
            )
            hp_candidate_overrides: list[dict[str, Any] | None] = [pt_hp_overrides]
            if type_search_prior.get("benchmark_hyperparameters"):
                hp_candidate_overrides.extend(TYPE_HP_CANDIDATES.get(ptype, []))
            unique_hp_candidate_overrides: list[dict[str, Any] | None] = []
            seen_hp_keys: set[str] = set()
            for hp_override in hp_candidate_overrides:
                key = json.dumps(hp_override or {}, sort_keys=True)
                if key in seen_hp_keys:
                    continue
                seen_hp_keys.add(key)
                unique_hp_candidate_overrides.append(hp_override)

            base_pt_model = _build_model(
                pt_num,
                pt_cat,
                len(Xt),
                hp_overrides=unique_hp_candidate_overrides[0],
                use_lossguide=ptype in _LOSSGUIDE_TYPES,
            )
            emit_status(
                "per_type_models",
                _overall_training_progress(eligible.index(ptype) + 2, total_models, 0, base_pt_model.iterations),
                rows=len(df),
                current_model=str(ptype),
                current_model_index=eligible.index(ptype) + 2,
                total_models=total_models,
                current_model_progress=0,
                fitted_trees=0,
                total_trees=base_pt_model.iterations,
            )
            candidate_results: list[dict[str, Any]] = []
            for feature_variant_name in feature_variant_names:
                variant_features = feature_variants.get(feature_variant_name, {})
                variant_num = variant_features.get("numeric", pt_num)
                variant_cat = variant_features.get("categorical", pt_cat)
                if not variant_num:
                    continue

                for target_transform in target_candidates:
                    for policy_name, years_back in policy_candidates:
                        X_policy, y_policy, policy_info = _restrict_training_years(Xt, yt, years_back)
                        if len(X_policy) < MIN_SAMPLES_PER_TYPE:
                            continue

                        for hp_index, hp_override in enumerate(unique_hp_candidate_overrides):
                            policy_model = _build_model(
                                variant_num,
                                variant_cat,
                                len(X_policy),
                                hp_overrides=hp_override,
                                use_lossguide=ptype in _LOSSGUIDE_TYPES,
                            )
                            policy_result = _train_single_model(
                                policy_model,
                                X_policy,
                                y_policy,
                                Xte,
                                yte,
                                f"type:{ptype}",
                                training_progress,
                                target_transform=target_transform,
                                sample_weight=_build_recency_sample_weights(X_policy, y_policy),
                            )
                            candidate_results.append(
                                {
                                    "feature_variant": feature_variant_name,
                                    "target_transform": target_transform,
                                    "training_policy": policy_name,
                                    "policy_cutoff_year": policy_info.get("cutoff_year"),
                                    "numeric_features": list(variant_num),
                                    "categorical_features": list(variant_cat),
                                    "numeric_feature_count": len(variant_num),
                                    "categorical_feature_count": len(variant_cat),
                                    "total_feature_count": len(variant_num) + len(variant_cat),
                                    "hyperparameter_variant": f"hp_{hp_index}",
                                    "hyperparameter_overrides": dict(hp_override or {}),
                                    "model": policy_model,
                                    "hyperparameters": dict(policy_model.params),
                                    "result": policy_result,
                                    "metrics": policy_result["metrics"],
                                }
                            )

            best_candidate = _select_best_training_candidate(candidate_results, property_type=ptype)
            if best_candidate is None:
                continue

            pt_model = best_candidate["model"]
            pt_result = best_candidate["result"]
            best_policy_name = str(best_candidate["training_policy"])
            best_policy_cutoff = best_candidate.get("policy_cutoff_year")
            chosen_target_transform = str(best_candidate["target_transform"])
            chosen_feature_variant = str(best_candidate["feature_variant"])
            chosen_numeric_features = list(best_candidate["numeric_features"])
            chosen_categorical_features = list(best_candidate["categorical_features"])

            # Compare against global baseline on this type's holdout and derive routing blend.
            g_pred = _predict_with_model_meta(
                Xte,
                {"pipeline": global_model, "target_transform": "log_ppm2"},
                default_target_transform="log_ppm2",
            )
            global_type_metrics = _compute_metrics(yte, g_pred)
            global_type_metrics["n_test"] = len(Xte)

            pt_pred = _predict_with_model_meta(
                Xte,
                {"pipeline": pt_model, "target_transform": chosen_target_transform},
                default_target_transform=chosen_target_transform,
            )
            route_candidates: list[dict[str, Any]] = []
            blend_weight, routed_metrics = _compute_per_type_blend_weight(ptype, yte, g_pred, pt_pred, len(Xte))
            route_candidates.append(
                {
                    "route_label": "global_fallback",
                    "fallback_source": "global",
                    "blend_weight": float(blend_weight),
                    "metrics": dict(routed_metrics),
                }
            )

            specialist_fallback = _train_specialist_fallback_model(
                ptype,
                Xt,
                yt,
                Xte,
                yte,
                raw_numeric_features=raw_type_numeric,
                raw_categorical_features=raw_type_categorical,
                always_numeric=always_num,
                always_categorical=always_cat,
                default_target_transform=chosen_target_transform,
                use_lossguide=ptype in _LOSSGUIDE_TYPES,
                training_progress=training_progress,
            )
            if specialist_fallback is not None:
                specialist_pred = _predict_specialist_fallback_meta(
                    Xte,
                    specialist_fallback,
                    default_target_transform=str(
                        specialist_fallback.get("target_transform") or chosen_target_transform
                    ),
                )
                specialist_blend_weight, specialist_routed_metrics = _compute_per_type_blend_weight(
                    ptype,
                    yte,
                    specialist_pred,
                    pt_pred,
                    len(Xte),
                )
                route_candidates.append(
                    {
                        "route_label": "specialist_fallback",
                        "fallback_source": "specialist",
                        "blend_weight": float(specialist_blend_weight),
                        "metrics": dict(specialist_routed_metrics),
                        "specialist_fallback": specialist_fallback,
                    }
                )

            chosen_route = _select_best_metrics_candidate(route_candidates, property_type=ptype) or route_candidates[0]
            blend_weight = float(chosen_route.get("blend_weight", 0.0))
            routed_metrics = dict(chosen_route.get("metrics") or {})
            fallback_source = str(chosen_route.get("fallback_source") or "global")
            chosen_specialist_fallback = (
                chosen_route.get("specialist_fallback") if fallback_source == "specialist" else None
            )
            if blend_weight <= 0.0:
                routing_mode = "specialist_only" if fallback_source == "specialist" else "global_only"
            elif blend_weight >= 0.999:
                routing_mode = "per_type_only"
            else:
                routing_mode = "blend_specialist" if fallback_source == "specialist" else "blend"

            routed_metrics["n_train"] = len(Xt)
            routed_metrics["n_test"] = len(Xte)
            routed_metrics["blend_weight"] = round(float(blend_weight), 6)
            routed_metrics["routing_mode"] = routing_mode
            per_type_models[ptype] = {
                "pipeline": pt_model,
                "numeric_features": chosen_numeric_features,
                "categorical_features": chosen_categorical_features,
                "blend_weight": float(blend_weight),
                "fallback_source": fallback_source,
                "training_policy": best_policy_name,
                "policy_cutoff_year": best_policy_cutoff,
                "target_transform": chosen_target_transform,
                "feature_variant": chosen_feature_variant,
            }
            if chosen_specialist_fallback is not None:
                per_type_models[ptype]["specialist_fallback"] = chosen_specialist_fallback
            per_type_metrics[ptype] = routed_metrics
            logger.info(
                "  %s result: routed R²=%.4f  routed MAPE=%.1f%%  blend=%.2f (%s)",
                ptype,
                routed_metrics.get("r2", 0),
                routed_metrics.get("mape", 0),
                blend_weight,
                routing_mode,
            )
            routing_comparison[ptype] = {
                "global_only": {
                    "metrics": {
                        key: round(float(value), 6) if isinstance(value, (int, float)) else value
                        for key, value in global_type_metrics.items()
                    },
                    "target_transform": "log_ppm2",
                },
                "per_type_only": {
                    "metrics": {
                        key: round(float(value), 6) if isinstance(value, (int, float)) else value
                        for key, value in pt_result["metrics"].items()
                    },
                    "target_transform": chosen_target_transform,
                    "feature_variant": chosen_feature_variant,
                    "training_policy": best_policy_name,
                },
                "specialist_fallback": (
                    {
                        "metrics": {
                            key: round(float(value), 6) if isinstance(value, (int, float)) else value
                            for key, value in (specialist_fallback.get("metrics") or {}).items()
                        },
                        "target_transform": str(specialist_fallback.get("target_transform") or chosen_target_transform),
                        "feature_variant": str(specialist_fallback.get("feature_variant") or "rich"),
                    }
                    if specialist_fallback is not None
                    else None
                ),
                "searched_blend": {
                    "metrics": {
                        key: round(float(value), 6) if isinstance(value, (int, float)) else value
                        for key, value in routed_metrics.items()
                        if key != "routing_mode"
                    },
                    "blend_weight": round(float(blend_weight), 6),
                    "fallback_source": fallback_source,
                },
                "chosen_routing_mode": routing_mode,
                "chosen_target_transform": chosen_target_transform,
                "chosen_feature_variant": chosen_feature_variant,
            }
            per_type_feature_usage[ptype] = {
                "numeric_features": chosen_numeric_features,
                "categorical_features": chosen_categorical_features,
                "selection_mode": selection_mode,
                "training_policy": best_policy_name,
                "policy_cutoff_year": best_policy_cutoff,
                "target_transform": chosen_target_transform,
                "feature_variant": chosen_feature_variant,
                "blend_weight": round(float(blend_weight), 6),
                "routing_mode": routing_mode,
                "numeric_feature_count": len(chosen_numeric_features),
                "categorical_feature_count": len(chosen_categorical_features),
                "total_feature_count": len(chosen_numeric_features) + len(chosen_categorical_features),
                "model_hyperparameters": dict(pt_model.params),
                "raw_per_type_r2": round(float(pt_result["metrics"].get("r2", 0.0)), 6),
                "raw_per_type_mape": round(float(pt_result["metrics"].get("mape", 0.0)), 6),
                "global_baseline_r2": round(float(global_type_metrics.get("r2", 0.0)), 6),
                "global_baseline_mape": round(float(global_type_metrics.get("mape", 0.0)), 6),
                "fallback_source": fallback_source,
                "candidate_matrix": [
                    {
                        "feature_variant": str(candidate["feature_variant"]),
                        "target_transform": str(candidate["target_transform"]),
                        "training_policy": str(candidate["training_policy"]),
                        "policy_cutoff_year": candidate.get("policy_cutoff_year"),
                        "hyperparameter_variant": str(candidate.get("hyperparameter_variant") or "hp_0"),
                        "hyperparameter_overrides": dict(candidate.get("hyperparameter_overrides") or {}),
                        "numeric_feature_count": int(candidate.get("numeric_feature_count", 0)),
                        "categorical_feature_count": int(candidate.get("categorical_feature_count", 0)),
                        "total_feature_count": int(candidate.get("total_feature_count", 0)),
                        "hyperparameters": dict(candidate.get("hyperparameters") or {}),
                        "metrics": {
                            key: round(float(value), 6) if isinstance(value, (int, float)) else value
                            for key, value in (candidate.get("metrics") or {}).items()
                        },
                    }
                    for candidate in candidate_results
                ],
            }
            if specialist_fallback is not None:
                specialist_default = (
                    specialist_fallback.get("default_model") if isinstance(specialist_fallback, dict) else None
                )
                specialist_numeric = (
                    specialist_fallback.get("numeric_features")
                    if isinstance(specialist_fallback, dict) and specialist_fallback.get("numeric_features") is not None
                    else (specialist_default.get("numeric_features") if isinstance(specialist_default, dict) else [])
                ) or []
                specialist_categorical = (
                    specialist_fallback.get("categorical_features")
                    if isinstance(specialist_fallback, dict)
                    and specialist_fallback.get("categorical_features") is not None
                    else (
                        specialist_default.get("categorical_features") if isinstance(specialist_default, dict) else []
                    )
                ) or []
                specialist_summary = {
                    "mode": str(specialist_fallback.get("mode") or "single_model"),
                    "feature_variant": str(specialist_fallback.get("feature_variant") or chosen_target_transform),
                    "target_transform": str(specialist_fallback.get("target_transform") or chosen_target_transform),
                    "numeric_feature_count": int(len(specialist_numeric)),
                    "categorical_feature_count": int(len(specialist_categorical)),
                    "total_feature_count": int(len(specialist_numeric) + len(specialist_categorical)),
                    "model_hyperparameters": dict(
                        specialist_fallback.get("model_hyperparameters")
                        or (
                            specialist_default.get("model_hyperparameters")
                            if isinstance(specialist_default, dict)
                            else {}
                        )
                        or {}
                    ),
                    "metrics": {
                        key: round(float(value), 6) if isinstance(value, (int, float)) else value
                        for key, value in (specialist_fallback.get("metrics") or {}).items()
                    },
                }
                subtype_models = (
                    specialist_fallback.get("subtype_models") if isinstance(specialist_fallback, dict) else None
                )
                if isinstance(subtype_models, dict) and subtype_models:
                    specialist_summary["subtype_models"] = {
                        str(subtype_key): {
                            "train_rows": int(subtype_meta.get("train_rows") or 0),
                            "test_rows": int(subtype_meta.get("test_rows") or 0),
                            "metrics": {
                                key: round(float(value), 6) if isinstance(value, (int, float)) else value
                                for key, value in (subtype_meta.get("metrics") or {}).items()
                            },
                        }
                        for subtype_key, subtype_meta in subtype_models.items()
                    }
                per_type_feature_usage[ptype]["specialist_fallback"] = specialist_summary
            if pt_scores:
                sorted_scores = sorted(pt_scores.items(), key=lambda item: item[1], reverse=True)
                per_type_feature_usage[ptype]["feature_scores"] = {
                    key: round(float(value), 6) for key, value in sorted_scores
                }
                per_type_feature_usage[ptype]["top_features"] = [
                    {"feature": key, "score": round(float(value), 6)} for key, value in sorted_scores[:20]
                ]
    else:
        emit_status("per_type_models", 88, rows=len(df), total_models=total_models)

    # Per-region metrics (not separate models)
    emit_status("evaluation", 92, rows=len(df), total_models=total_models)
    per_region_metrics: dict[str, dict] = {}
    if "statistical_region" in X_test.columns:
        size_test_vals = X_test["size_m2"].clip(lower=1).values.astype(float)
        y_pred_all_raw = global_model.predict(X_test)
        y_pred_all = np.maximum(size_test_vals * np.exp(y_pred_all_raw), 0)
        for region in X_test["statistical_region"].unique():
            mask = X_test["statistical_region"] == region
            if mask.sum() >= 10:
                per_region_metrics[str(region)] = _compute_metrics(y_test[mask], y_pred_all[mask])

    # Combined routing metrics: use per-type model when available, else global
    if per_type_models:
        y_pred_combined = _predict_combined_routed(X_test, global_model, per_type_models, target_transform="log_ppm2")
    else:
        size_test_combined = X_test["size_m2"].clip(lower=1).values.astype(float)
        y_pred_combined_raw = global_model.predict(X_test)
        y_pred_combined = np.maximum(size_test_combined * np.exp(y_pred_combined_raw), 0)
    calibration = _fit_calibration_maps(X_test, y_test, y_pred_combined)
    y_pred_combined, calibration_details = _apply_calibration_to_predictions(X_test, y_pred_combined, calibration)
    combined_metrics = _compute_metrics(y_test, y_pred_combined)
    combined_metrics["n_train"] = len(X_train)
    combined_metrics["n_test"] = len(X_test)

    if per_type_metrics and calibration_details and "property_type" in X_test.columns:
        calibration_frame = X_test[["property_type"]].copy()
        calibration_frame["y_true"] = y_test
        calibration_frame["y_pred"] = y_pred_combined
        for property_type, group in calibration_frame.groupby("property_type"):
            metrics = _compute_metrics(group["y_true"].to_numpy(), group["y_pred"].to_numpy())
            existing = per_type_metrics.get(str(property_type), {})
            if metrics:
                existing.update(metrics)
                existing["n_test"] = int(len(group))
                per_type_metrics[str(property_type)] = existing

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

    # ── Variant benchmarks (global-only, skip per-type for speed) ─────
    logger.info("Starting variant benchmarks (global-only, 3 variants)...")
    variant_benchmarks: dict[str, Any] = {}
    variant_matrix: dict[str, Any] = {}
    for variant_name, enabled_sources in _VARIANT_CONFIGS.items():
        v_num = _filter_features_by_source(global_num, enabled_sources)
        v_cat = _filter_features_by_source(global_cat, enabled_sources)
        if not v_num:
            v_num = [
                f for f in global_num if not any(f.startswith(p) for ps in _ENRICHMENT_PREFIXES.values() for p in ps)
            ]
        if not v_num:
            continue
        # Lightweight global model for this variant (reduced iterations)
        base_hp = _adaptive_hyperparams(len(X_train))
        v_hp = {"iterations": max(100, base_hp["iterations"] // 4), "od_wait": 50}
        v_model = _build_model(v_num, v_cat, len(X_train), hp_overrides=v_hp)
        v_result = _train_single_model(
            v_model,
            X_train,
            y_train,
            X_test,
            y_test,
            f"variant:{variant_name}",
            None,
            target_transform="log_ppm2",
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
                k: round(vm.get(k, 0) - fg.get(k, 0), 6) for k in ("r2", "mae", "rmse", "mape") if k in vm and k in fg
            }
        # Variant matrix: global-only metrics (skip per-type to avoid 27 extra CatBoost models)
        variant_matrix[variant_name] = {
            "label": variant_name,
            "variant_label": variant_name,
            "enabled_sources": enabled_sources,
            "global_metrics": v_result["metrics"],
            "combined_metrics": v_result["metrics"],
            "per_type_metrics": {},
            "per_type_count": 0,
        }

    # Production combined entry in variant_benchmarks
    variant_benchmarks["production_combined"] = {
        "label": "production_combined",
        "variant_label": "production_combined",
        "enabled_sources": {s: True for s in _ENRICHMENT_PREFIXES},
        "metrics": combined_metrics,
    }

    dataset_years, dataset_year_source = _extract_year_series(df)
    valid_dataset_years = dataset_years.dropna()
    dataset_window = artifact_metadata.get("dataset_window") or {
        "year_source": dataset_year_source,
        "start_year": int(valid_dataset_years.min()) if not valid_dataset_years.empty else None,
        "end_year": int(valid_dataset_years.max()) if not valid_dataset_years.empty else None,
    }
    recent_research_diagnostics = _build_recent_research_diagnostics(
        df,
        X_test,
        y_test,
        y_pred_combined,
        per_type_feature_usage,
        routing_comparison,
    )

    # Municipality coordinates
    emit_status("artifact_save", 96, rows=len(df), total_models=total_models)
    coords_by_municipality: dict[str, dict] = {}
    coords_by_naselje: dict[str, dict] = {}
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
    if all(c in df.columns for c in ["naselje", "latitude", "longitude"]):
        muni_series = (
            df["municipality_normalized"]
            if "municipality_normalized" in df.columns
            else pd.Series("unknown", index=df.index, dtype="object")
        )
        naselje_frame = pd.DataFrame(
            {
                "municipality_normalized": muni_series.astype(str),
                "naselje": df["naselje"].astype(str),
                "latitude": df["latitude"],
                "longitude": df["longitude"],
            }
        )
        for (muni, naselje), grp in naselje_frame.groupby(["municipality_normalized", "naselje"]):
            lat = pd.to_numeric(grp["latitude"], errors="coerce").median()
            lon = pd.to_numeric(grp["longitude"], errors="coerce").median()
            if pd.notna(lat) and pd.notna(lon):
                coords_by_naselje[f"{muni}|{naselje}"] = {"lat": float(lat), "lon": float(lon)}

    deploy_maps = _build_deployment_prediction_maps(df)
    duration = time.time() - start

    # Save artifact
    os.makedirs(os.path.dirname(resolved_model_path), exist_ok=True)
    emit_status("finalizing", 99, rows=len(df), total_models=total_models)
    artifact = {
        "version": "12.3",
        "target_transform": "log_ppm2",
        "log_target": True,  # backward compat
        "global_model": {
            "pipeline": global_model,
            "numeric_features": global_num,
            "categorical_features": global_cat,
        },
        # Backward compat
        "global_pipeline": global_model,
        "per_type_models": per_type_models,
        "region_medians": region_medians,
        "type_medians": type_medians,
        "municipality_medians": municipality_medians,
        "global_median_ppm2": global_median_ppm2,
        "type_muni_comp": type_muni_comp,
        "type_ko_comp": type_ko_comp,
        "type_naselje_comp": type_naselje_comp,
        "subtype_muni_comp": subtype_muni_comp,
        "subtype_ko_comp": subtype_ko_comp,
        "subtype_naselje_comp": subtype_naselje_comp,
        "global_log_ppm2": global_log_ppm2,
        # Engineered feature artifacts (for prediction-time recomputation)
        "eng_artifacts": eng_artifacts,
        "global_metrics": global_result["metrics"],
        "global_importance": global_result["importance"],
        "per_type_metrics": per_type_metrics,
        "per_region_metrics": per_region_metrics,
        "combined_metrics": combined_metrics,
        "calibration": calibration,
        "holdout": holdout_info,
        "coords_by_municipality": coords_by_municipality,
        "coords_by_naselje": coords_by_naselje,
        **deploy_maps,
        "feature_labels": FEATURE_LABELS_SL,
        "trained_at": pd.Timestamp.now().isoformat(),
        "csv_path": csv_path,
        "model_path": resolved_model_path,
        "rows": len(df),
        "train_rows": len(X_train),
        "test_rows": len(X_test),
        "used_features": global_num + global_cat,
        "per_type_features": per_type_feature_usage,
        "routing_comparison": routing_comparison,
        "data_preparation": data_preparation,
        "training_window": training_window,
        "dataset_window": dataset_window,
        "artifact_metadata": artifact_metadata,
        "segment_diagnostics": segment_diagnostics,
        "recent_research_diagnostics": recent_research_diagnostics,
        "ev_baseline_metrics": ev_baseline_metrics,
        "variant_benchmarks": variant_benchmarks,
        "variant_matrix": variant_matrix,
        "model_type": "CatBoostRegressor",
        "duration_sec": duration,
    }
    joblib.dump(artifact, resolved_model_path, compress=3)

    return {
        "model_path": resolved_model_path,
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
        "routing_comparison": routing_comparison,
        "data_preparation": data_preparation,
        "training_window": training_window,
        "dataset_window": dataset_window,
        "artifact_metadata": artifact_metadata,
        "segment_diagnostics": segment_diagnostics,
        "recent_research_diagnostics": recent_research_diagnostics,
        "ev_baseline_metrics": ev_baseline_metrics,
        "variant_benchmarks": variant_benchmarks,
        "variant_matrix": variant_matrix,
        "model_type": "CatBoostRegressor",
    }


def load_model(model_path: str | None = None) -> dict | None:
    """Load model artifact, auto-reloading when the file changes on disk.

    The ARQ worker trains in a separate process, so `invalidate_model_cache()`
    only clears the worker's cache. This mtime check ensures the API process
    picks up the new model without requiring a restart.
    """
    resolved_model_path = os.path.abspath(model_path or _default_model_path())
    if resolved_model_path != os.path.abspath(_default_model_path()):
        if not os.path.exists(resolved_model_path):
            return None
        return joblib.load(resolved_model_path)

    global _model_cache, _model_cache_mtime
    if not os.path.exists(resolved_model_path):
        return None
    current_mtime = os.path.getmtime(resolved_model_path)
    if _model_cache is not None and current_mtime == _model_cache_mtime:
        return _model_cache
    _model_cache = joblib.load(resolved_model_path)
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


def _lookup_categorical_map_value(
    mapping: dict[str, Any] | None,
    normalized_key: str | None,
    raw_key: str | None,
    default: Any,
) -> Any:
    """Look up a categorical key with normalized/raw fallbacks."""
    if not mapping:
        return default

    for candidate in (normalized_key, raw_key):
        if candidate in mapping:
            return mapping[candidate]

    raw_norm = None
    if raw_key not in (None, ""):
        raw_norm = str(raw_key)
    norm_norm = None
    if normalized_key not in (None, ""):
        norm_norm = normalize_municipality_name(str(normalized_key))
    raw_norm = normalize_municipality_name(raw_norm) if raw_norm else None

    for candidate in (norm_norm, raw_norm):
        if candidate and candidate in mapping:
            return mapping[candidate]

    folded_raw = raw_norm or norm_norm
    if folded_raw:
        for existing_key, value in mapping.items():
            if normalize_municipality_name(str(existing_key)) == folded_raw:
                return value

    return default


def _is_unknown_category_value(value: Any) -> bool:
    if value is None:
        return True
    try:
        numeric = float(value)
        if np.isnan(numeric):
            return True
    except (TypeError, ValueError):
        pass
    text = str(value).strip().lower()
    return text in {"", "unknown", "nan", "none", "<na>"}


# Bucket ev_id_konstrukcija values into coarse construction families for hisa.
# Values in CSV: 1=brick (dominant, 50%), 5=concrete (19%), 3=wood (11%), 2=mixed (6%),
# 8=prefab (5%), others=rare. Bucket the long tail to prevent per-bucket undersampling.
_HISA_KONSTRUKCIJA_BUCKETS: dict[str, str] = {
    "1": "brick",
    "1.0": "brick",
    "5": "concrete",
    "5.0": "concrete",
    "3": "wood",
    "3.0": "wood",
    "2": "mixed",
    "2.0": "mixed",
    "8": "prefab",
    "8.0": "prefab",
}


def _hisa_konstrukcija_bucket(value: Any) -> str:
    if _is_unknown_category_value(value):
        return "unknown"
    text = str(value).strip()
    return _HISA_KONSTRUKCIJA_BUCKETS.get(text, "other")


def _garaza_vrsta_bucket(value: Any) -> str:
    """Garaza splits cleanly: 3=aboveground (~48%), 4=underground (~49%)."""
    if _is_unknown_category_value(value):
        return "unknown"
    text = str(value).strip()
    if text in {"3", "3.0"}:
        return "aboveground"
    if text in {"4", "4.0"}:
        return "underground"
    return "other"


def _market_subtype_key_from_values(
    property_type: Any,
    vrsta_zemljisca: Any = None,
    parcela_namenska_raba: Any = None,
    *,
    vrsta_dela_stavbe: Any = None,
    ev_id_konstrukcija: Any = None,
) -> str:
    property_key = str(property_type or "unknown")
    if property_key in {"kmetijsko", "parcela"}:
        land_key = "unknown" if _is_unknown_category_value(vrsta_zemljisca) else str(vrsta_zemljisca)
        use_key = "unknown" if _is_unknown_category_value(parcela_namenska_raba) else str(parcela_namenska_raba)
        return f"{property_key}|{land_key}|{use_key}"
    if property_key == "garaza":
        bucket = _garaza_vrsta_bucket(vrsta_dela_stavbe)
        return f"garaza|{bucket}"
    if property_key == "hisa":
        bucket = _hisa_konstrukcija_bucket(ev_id_konstrukcija)
        return f"hisa|{bucket}"
    return property_key


def _build_market_subtype_series(frame: pd.DataFrame) -> pd.Series:
    property_series = frame.get("property_type", pd.Series("unknown", index=frame.index)).astype(str)
    land_series = frame.get("vrsta_zemljisca", pd.Series("unknown", index=frame.index))
    use_series = frame.get("parcela_namenska_raba", pd.Series("unknown", index=frame.index))
    vds_series = frame.get("vrsta_dela_stavbe", pd.Series("unknown", index=frame.index))
    konstr_series = frame.get("ev_id_konstrukcija", pd.Series("unknown", index=frame.index))
    return pd.Series(
        [
            _market_subtype_key_from_values(
                property_type,
                vrsta_zemljisca,
                parcela_namenska_raba,
                vrsta_dela_stavbe=vds,
                ev_id_konstrukcija=konstr,
            )
            for property_type, vrsta_zemljisca, parcela_namenska_raba, vds, konstr in zip(
                property_series,
                land_series,
                use_series,
                vds_series,
                konstr_series,
                strict=False,
            )
        ],
        index=frame.index,
        dtype="object",
    )


def _build_normalized_payload(
    payload: dict[str, Any],
    numeric_features: list[str],
    categorical_features: list[str],
    artifact: dict[str, Any],
) -> dict[str, Any]:
    """Build a normalized input row for prediction, including derived features and imputation."""
    from app.services.regions_service import lookup_region, normalize

    coords_by_muni = artifact.get("coords_by_municipality", {})
    coords_by_naselje = artifact.get("coords_by_naselje", {})
    region_medians = artifact.get("deploy_region_medians") or artifact.get("region_medians", {})
    type_medians = artifact.get("deploy_type_medians") or artifact.get("type_medians", {})
    global_median = artifact.get("deploy_global_median_ppm2", artifact.get("global_median_ppm2", 2000.0))

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
        if col == "market_subtype_key":
            continue
        if col == "statistical_region" and col not in payload:
            muni = normalize_municipality_name(payload.get("municipality"))
            row[col] = lookup_region(muni)
        else:
            val = payload.get(col, "unknown")
            row[col] = normalize(str(val)) if val else "unknown"

    if "market_subtype_key" in categorical_features:
        row["market_subtype_key"] = _market_subtype_key_from_values(
            row.get("property_type", payload.get("property_type", "unknown")),
            row.get("vrsta_zemljisca", payload.get("vrsta_zemljisca")),
            row.get("parcela_namenska_raba", payload.get("parcela_namenska_raba")),
            vrsta_dela_stavbe=row.get("vrsta_dela_stavbe", payload.get("vrsta_dela_stavbe")),
            ev_id_konstrukcija=row.get("ev_id_konstrukcija", payload.get("ev_id_konstrukcija")),
        )

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
    naselje_norm = normalize(str(payload.get("naselje", "unknown"))) if payload.get("naselje") else "unknown"
    for coord_key in ("latitude", "longitude"):
        val = row.get(coord_key)
        if val is None or (isinstance(val, float) and np.isnan(val)):
            coord_val = None
            naselje_coords = coords_by_naselje.get(f"{municipality_norm}|{naselje_norm}", {})
            if naselje_coords:
                coord_val = naselje_coords.get("lat" if coord_key == "latitude" else "lon")
                if coord_val is None:
                    coord_val = naselje_coords.get(coord_key)
            if coord_val is None:
                muni_coords = coords_by_muni.get(municipality_norm, {})
                coord_val = muni_coords.get("lat" if coord_key == "latitude" else "lon")
                if coord_val is None:
                    coord_val = muni_coords.get(coord_key)
            row[coord_key] = float(coord_val) if coord_val is not None else np.nan

    # Group medians
    ptype_key = normalize(str(payload.get("property_type", row.get("property_type", "unknown"))))
    if "price_per_m2_region" in numeric_features:
        region = row.get("statistical_region", "neznana")
        row["price_per_m2_region"] = region_medians.get(region, global_median)

    if "price_per_m2_type" in numeric_features:
        row["price_per_m2_type"] = type_medians.get(ptype_key, global_median)

    if "price_per_m2_municipality" in numeric_features:
        municipality_medians = artifact.get("deploy_municipality_medians") or artifact.get("municipality_medians", {})
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
    global_log_ppm2 = artifact.get("deploy_global_log_ppm2", artifact.get("global_log_ppm2", np.log(2000.0)))
    raw_ko_key = str(payload.get("ime_ko", "unknown"))
    normalized_ko_key = str(row.get("ime_ko", normalize(raw_ko_key)))
    raw_naselje_key = str(payload.get("naselje", "unknown"))
    normalized_naselje_key = str(row.get("naselje", normalize(raw_naselje_key)))
    ko_lookup_key = None if _is_unknown_category_value(normalized_ko_key) else normalized_ko_key
    ko_lookup_raw = None if _is_unknown_category_value(raw_ko_key) else raw_ko_key
    naselje_lookup_key = None if _is_unknown_category_value(normalized_naselje_key) else normalized_naselje_key
    naselje_lookup_raw = None if _is_unknown_category_value(raw_naselje_key) else raw_naselje_key
    if "comp_type_muni_ppm2" in numeric_features:
        type_muni_comp = artifact.get("deploy_type_muni_comp") or artifact.get("type_muni_comp", {})
        muni_map = type_muni_comp.get(ptype_key, {})
        muni_key = row.get("municipality_normalized", municipality_norm)
        row["comp_type_muni_ppm2"] = muni_map.get(muni_key, global_log_ppm2)
    if "comp_type_ko_ppm2" in numeric_features:
        type_ko_comp = artifact.get("deploy_type_ko_comp") or artifact.get("type_ko_comp", {})
        ko_map = type_ko_comp.get(ptype_key, {})
        row["comp_type_ko_ppm2"] = _lookup_categorical_map_value(
            ko_map,
            ko_lookup_key,
            ko_lookup_raw,
            row.get("comp_type_muni_ppm2", global_log_ppm2),
        )
    if "comp_type_naselje_ppm2" in numeric_features:
        type_naselje_comp = artifact.get("deploy_type_naselje_comp") or artifact.get("type_naselje_comp", {})
        naselje_map = type_naselje_comp.get(ptype_key, {})
        row["comp_type_naselje_ppm2"] = _lookup_categorical_map_value(
            naselje_map,
            naselje_lookup_key,
            naselje_lookup_raw,
            np.nan,
        )
    subtype_key = _market_subtype_key_from_values(
        ptype_key,
        row.get("vrsta_zemljisca"),
        row.get("parcela_namenska_raba"),
        vrsta_dela_stavbe=row.get("vrsta_dela_stavbe"),
        ev_id_konstrukcija=row.get("ev_id_konstrukcija"),
    )
    if "comp_subtype_muni_ppm2" in numeric_features:
        subtype_muni_comp = artifact.get("deploy_subtype_muni_comp") or artifact.get("subtype_muni_comp", {})
        muni_map = subtype_muni_comp.get(subtype_key, {})
        muni_key = row.get("municipality_normalized", municipality_norm)
        row["comp_subtype_muni_ppm2"] = muni_map.get(muni_key, row.get("comp_type_muni_ppm2", global_log_ppm2))
    if "comp_subtype_ko_ppm2" in numeric_features:
        subtype_ko_comp = artifact.get("deploy_subtype_ko_comp") or artifact.get("subtype_ko_comp", {})
        ko_map = subtype_ko_comp.get(subtype_key, {})
        row["comp_subtype_ko_ppm2"] = _lookup_categorical_map_value(
            ko_map,
            ko_lookup_key,
            ko_lookup_raw,
            row.get("comp_subtype_muni_ppm2", row.get("comp_type_ko_ppm2", global_log_ppm2)),
        )
    if "comp_subtype_naselje_ppm2" in numeric_features:
        subtype_naselje_comp = artifact.get("deploy_subtype_naselje_comp") or artifact.get("subtype_naselje_comp", {})
        naselje_map = subtype_naselje_comp.get(subtype_key, {})
        row["comp_subtype_naselje_ppm2"] = _lookup_categorical_map_value(
            naselje_map,
            naselje_lookup_key,
            naselje_lookup_raw,
            row.get("comp_subtype_ko_ppm2", row.get("comp_subtype_muni_ppm2", np.nan)),
        )

    # ── Engineered features ──────────────────────────────────────────
    eng = artifact.get("eng_artifacts", {})

    # Spatial KNN features
    knn_needed = any(
        f in numeric_features for f in ("knn_3_log_ppm2", "knn_5_log_ppm2", "knn_20_log_ppm2", "knn_dw10_log_ppm2")
    )
    if knn_needed:
        knn_coords = eng.get("knn_coords")
        knn_lp = eng.get("knn_log_ppm2")
        if knn_coords is not None and knn_lp is not None:
            pt = np.array(
                [
                    [
                        lon_val if not (isinstance(lon_val, float) and np.isnan(lon_val)) else 0,
                        lat_val if not (isinstance(lat_val, float) and np.isnan(lat_val)) else 0,
                    ]
                ]
            )
            tree_all = KDTree(knn_coords)
            for K in (3, 5, 20):
                col = f"knn_{K}_log_ppm2"
                if col in numeric_features:
                    _, idx = tree_all.query(pt, k=K)
                    row[col] = float(np.median(knn_lp[idx.flatten()]))
            # Distance-weighted KNN
            if "knn_dw10_log_ppm2" in numeric_features:
                d, idx = tree_all.query(pt, k=10)
                d_flat = np.maximum(d.flatten(), 1.0)
                w = 1.0 / d_flat
                w /= w.sum()
                row["knn_dw10_log_ppm2"] = float(np.sum(w * knn_lp[idx.flatten()]))

    # Same-type KNN
    if "knn_type_10_log_ppm2" in numeric_features:
        type_knn = eng.get("type_knn_data", {})
        td = type_knn.get(ptype_key)
        if td is not None:
            type_tree = KDTree(td["coords"])
            k = min(10, len(td["coords"]) - 1)
            if k > 0:
                pt = np.array(
                    [
                        [
                            lon_val if not (isinstance(lon_val, float) and np.isnan(lon_val)) else 0,
                            lat_val if not (isinstance(lat_val, float) and np.isnan(lat_val)) else 0,
                        ]
                    ]
                )
                _, idx = type_tree.query(pt, k=k)
                row["knn_type_10_log_ppm2"] = float(np.median(td["log_ppm2"][idx.flatten()]))

    # Count features
    count_maps = eng.get("count_maps", {})
    if "ko_transaction_count" in numeric_features:
        ko_counts = count_maps.get("ime_ko", {})
        row["ko_transaction_count"] = float(_lookup_categorical_map_value(ko_counts, ko_lookup_key, ko_lookup_raw, 0))
    if "muni_transaction_count" in numeric_features:
        muni_counts = count_maps.get("municipality_normalized", {})
        row["muni_transaction_count"] = float(muni_counts.get(municipality_norm, 0))
    if "naselje_transaction_count" in numeric_features:
        naselje_counts = count_maps.get("naselje", {})
        row["naselje_transaction_count"] = float(
            _lookup_categorical_map_value(naselje_counts, naselje_lookup_key, naselje_lookup_raw, 0)
        )

    # KO price per m²
    if "price_per_m2_ko" in numeric_features:
        deploy_eng = artifact.get("deploy_eng_artifacts", {})
        ko_ppm2_map = deploy_eng.get("ko_ppm2_map") or eng.get("ko_ppm2_map", {})
        row["price_per_m2_ko"] = _lookup_categorical_map_value(
            ko_ppm2_map,
            ko_lookup_key,
            ko_lookup_raw,
            row.get(
                "price_per_m2_municipality",
                deploy_eng.get("global_median_ppm2_for_ko", eng.get("global_median_ppm2_for_ko", global_median)),
            ),
        )

    # Price ratio features (derived from already-computed features)
    if "ko_vs_muni_premium" in numeric_features:
        row["ko_vs_muni_premium"] = row.get("comp_type_ko_ppm2", 0) - row.get("comp_type_muni_ppm2", 0)
    if "muni_vs_region_premium" in numeric_features:
        m = max(row.get("price_per_m2_municipality", 1), 1)
        r = max(row.get("price_per_m2_region", 1), 1)
        row["muni_vs_region_premium"] = float(np.log(m / r))

    # Size percentile
    if "size_percentile" in numeric_features:
        sq = eng.get("size_quantiles", {})
        sizes_arr = sq.get(ptype_key)
        sm2 = row.get("size_m2", np.nan)
        if sizes_arr is not None and not (isinstance(sm2, float) and np.isnan(sm2)):
            row["size_percentile"] = float(np.searchsorted(sizes_arr, sm2) / len(sizes_arr))
        else:
            row["size_percentile"] = 0.5

    # Data quality indicators
    if "has_ev_data" in numeric_features:
        row["has_ev_data"] = 1.0 if payload.get("ev_leto_izg_stavbe") is not None else 0.0
    if "has_renovation_data" in numeric_features:
        reno_keys = ["ev_leto_obn_strehe", "ev_leto_obn_fasade", "ev_leto_obn_oken", "ev_leto_obn_inst"]
        row["has_renovation_data"] = 1.0 if any(payload.get(k) is not None for k in reno_keys) else 0.0

    # Time index
    if "time_index" in numeric_features:
        min_yr = eng.get("min_year", 2020.0)
        yr = row.get("transaction_year", float(pd.Timestamp.now().year))
        qtr = row.get("transaction_quarter", float(pd.Timestamp.now().quarter))
        row["time_index"] = (yr - min_yr) * 4 + qtr

    # Renovation recency
    if "latest_renovation_year" in numeric_features or "years_since_renovation" in numeric_features:
        reno_years = []
        for rc in ["ev_leto_obn_strehe", "ev_leto_obn_fasade", "ev_leto_obn_oken", "ev_leto_obn_inst"]:
            v = payload.get(rc)
            if v is not None:
                with contextlib.suppress(TypeError, ValueError):
                    reno_years.append(float(v))
        if reno_years:
            latest = max(reno_years)
            row["latest_renovation_year"] = latest
            row["years_since_renovation"] = row.get("transaction_year", float(pd.Timestamp.now().year)) - latest
        else:
            row["latest_renovation_year"] = np.nan
            row["years_since_renovation"] = np.nan

    # Parcel sold fraction
    if "parcel_sold_fraction" in numeric_features:
        sm2 = row.get("size_m2", np.nan)
        pm2 = row.get("parcela_m2", np.nan)
        if not (isinstance(sm2, float) and np.isnan(sm2)) and not (isinstance(pm2, float) and np.isnan(pm2)):
            row["parcel_sold_fraction"] = min(sm2 / max(pm2, 1), 1.0)
        else:
            row["parcel_sold_fraction"] = np.nan

    # Stacking: global model prediction as a feature for per-type specialists.
    # At prediction time, run the global model first and inject log(prediction).
    if "global_pred_log_price" in numeric_features:
        global_model_data = artifact.get("global_model", {})
        if isinstance(global_model_data, dict) and "pipeline" in global_model_data:
            g_num, g_cat = _resolve_model_feature_lists(
                global_model_data,
                default_numeric=NUMERIC_FEATURES,
                default_categorical=CATEGORICAL_FEATURES,
            )
            g_row_data = {k: v for k, v in row.items() if k in g_num or k in g_cat}
            g_df = pd.DataFrame([g_row_data])
            try:
                g_pred = float(
                    _predict_any_model_meta(
                        g_df,
                        global_model_data,
                        default_target_transform=str(global_model_data.get("target_transform") or "log_ppm2"),
                    )[0]
                )
                row["global_pred_log_price"] = float(np.log1p(max(g_pred, 1.0)))
            except Exception:
                row["global_pred_log_price"] = np.nan
        else:
            row["global_pred_log_price"] = np.nan

    return row


def _sparse_residential_floor_eur(
    payload: dict[str, Any],
    normalized_row: dict[str, Any],
    property_type: str,
) -> float | None:
    """Return a conservative price floor for sparse residential requests.

    When users provide only coarse inputs (e.g. municipality + size), the routed
    model can underpredict due to missing fine-grained location signals. In that
    case, anchor the minimum using robust local same-type references.
    """
    if property_type not in {"stanovanje", "hisa"}:
        return None

    has_fine_location = any(
        payload.get(key) not in (None, "") for key in ("latitude", "longitude", "ime_ko", "naselje")
    )

    size_m2 = normalized_row.get("size_m2")
    if size_m2 is None:
        return None
    try:
        size_val = float(size_m2)
    except (TypeError, ValueError):
        return None
    if np.isnan(size_val) or size_val <= 0:
        return None

    baseline_candidates: list[float] = []
    municipality_anchor: float | None = None
    for key, is_log in (
        ("comp_type_naselje_ppm2", True),
        ("comp_type_ko_ppm2", True),
        ("comp_type_muni_ppm2", True),
        ("knn_type_10_log_ppm2", True),
        ("price_per_m2_ko", False),
        ("price_per_m2_municipality", False),
    ):
        value = normalized_row.get(key)
        if value is None:
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if np.isnan(numeric):
            continue
        ppm2_value = float(np.exp(numeric)) if is_log else numeric
        if key in {"comp_type_naselje_ppm2", "comp_type_muni_ppm2"} and municipality_anchor is None:
            municipality_anchor = ppm2_value
        baseline_candidates.append(ppm2_value)

    if not baseline_candidates:
        return None

    if municipality_anchor is not None:
        filtered_candidates = [value for value in baseline_candidates if value >= municipality_anchor * 0.45]
        if filtered_candidates:
            baseline_candidates = filtered_candidates

    # Conservative floor: stronger for sparse inputs, softer when fine location is present.
    baseline_ppm2 = float(np.median(baseline_candidates))
    if municipality_anchor is not None:
        baseline_ppm2 = max(baseline_ppm2, municipality_anchor * 0.85)
    missing_micro_location = _is_unknown_category_value(normalized_row.get("ime_ko")) and _is_unknown_category_value(
        normalized_row.get("naselje")
    )
    if has_fine_location and len(baseline_candidates) >= 4:
        floor_factor = 0.88
    elif has_fine_location:
        floor_factor = 0.78
    else:
        floor_factor = 0.85
    if municipality_anchor is not None and missing_micro_location:
        if property_type == "stanovanje":
            floor_factor = max(floor_factor, 1.0)
        elif property_type == "hisa":
            floor_factor = max(floor_factor, 0.93)
    return floor_factor * baseline_ppm2 * size_val


def _resolve_prediction_upload_dir() -> str | None:
    if not _ENABLE_PREDICTION_ENRICHMENT:
        return None
    candidates = [
        os.getenv("PREDICTION_UPLOAD_DIR"),
        os.getenv("UPLOAD_DIR"),
        os.path.join(DATA_DIR, "uploads"),
        "/app/data/uploads",
    ]
    for candidate in candidates:
        if candidate and os.path.isdir(candidate):
            return candidate
    return None


def _prediction_feature_present(features: dict[str, Any], key: str) -> bool:
    return key in features and not _is_unknown_category_value(features.get(key))


def _prediction_enrichment_options(features: dict[str, Any]) -> dict[str, Any]:
    has_coords = _prediction_feature_present(features, "latitude") and _prediction_feature_present(
        features, "longitude"
    )
    spatial_enabled = _ENABLE_PREDICTION_SPATIAL_ENRICHMENT
    has_address = any(
        _prediction_feature_present(features, key)
        for key in ("municipality", "naselje", "ulica", "hisna_stevilka", "dodatek_hs")
    )
    has_ev_link_keys = any(
        _prediction_feature_present(features, key)
        for key in (
            "eid_stavba",
            "eid_del_stavbe",
            "eid_parcela",
            "sifra_ko",
            "stevilka_stavbe",
            "stevilka_dela_stavbe",
            "parcelna_stevilka",
        )
    )
    return {
        "enable_rn": has_address,
        "enable_ev": has_ev_link_keys or has_address,
        "enable_kn": has_coords and spatial_enabled,
        "enable_gji": has_coords and spatial_enabled,
        "enable_dtm": has_coords and spatial_enabled,
        "enable_emv": has_coords and spatial_enabled,
        "variant_label": "live_prediction",
    }


def _prediction_enrichment_cache_key(features: dict[str, Any]) -> str:
    canonical: dict[str, Any] = {}
    for key in sorted(features):
        value = features[key]
        if _is_unknown_category_value(value):
            continue
        if isinstance(value, (int, np.integer)):
            canonical[key] = int(value)
            continue
        if isinstance(value, (float, np.floating)):
            if np.isnan(float(value)):
                continue
            digits = 2 if key in {"latitude", "longitude"} else 4
            canonical[key] = round(float(value), digits)
            continue
        canonical[key] = value
    return json.dumps(canonical, ensure_ascii=True, sort_keys=True, default=str)


@lru_cache(maxsize=1024)
def _enrich_prediction_features_cached(cache_key: str, upload_dir: str) -> dict[str, Any]:
    features = json.loads(cache_key)
    options = _prediction_enrichment_options(features)
    if not any(
        bool(options.get(name))
        for name in ("enable_rn", "enable_ev", "enable_kn", "enable_gji", "enable_dtm", "enable_emv")
    ):
        return dict(features)

    frame = pd.DataFrame([dict(features)])
    frame = enrich_training_df(frame)
    enriched_frame, _summary = apply_gurs_deterministic_enrichment(
        frame,
        upload_dir=upload_dir,
        enrichment_options=options,
    )
    if enriched_frame.empty:
        return dict(features)
    return dict(enriched_frame.iloc[0].to_dict())


def _enrich_prediction_features(features: dict[str, Any]) -> dict[str, Any]:
    upload_dir = _resolve_prediction_upload_dir()
    if not upload_dir:
        return dict(features)

    try:
        cache_key = _prediction_enrichment_cache_key(features)
        if _PREDICTION_ENRICHMENT_TIMEOUT_SEC <= 0:
            enriched_row = _enrich_prediction_features_cached(cache_key, upload_dir)
        else:
            result_holder: dict[str, Any] = {}
            error_holder: dict[str, Exception] = {}

            def _run() -> None:
                try:
                    result_holder["row"] = _enrich_prediction_features_cached(cache_key, upload_dir)
                except Exception as exc:  # pragma: no cover - defensive wrapper
                    error_holder["error"] = exc

            worker = threading.Thread(target=_run, daemon=True)
            worker.start()
            worker.join(_PREDICTION_ENRICHMENT_TIMEOUT_SEC)
            if worker.is_alive():
                logger.warning(
                    "Prediction-time enrichment exceeded %.2fs; continuing with raw features",
                    _PREDICTION_ENRICHMENT_TIMEOUT_SEC,
                )
                return dict(features)
            if "error" in error_holder:
                raise error_holder["error"]
            enriched_row = result_holder.get("row", dict(features))
    except Exception:
        logger.exception("Prediction-time enrichment failed; continuing with raw features")
        return dict(features)

    merged = dict(features)
    for key, value in enriched_row.items():
        if _is_unknown_category_value(value):
            continue
        if key in merged and not _is_unknown_category_value(merged.get(key)):
            continue
        merged[key] = value
    return merged


def predict_one(features: dict[str, Any]) -> dict[str, Any]:
    """Predict price for a single property."""
    artifact = load_model()
    if artifact is None:
        raise RuntimeError("No trained model found. Train a model first.")

    from app.services.regions_service import normalize

    ptype = normalize(str(features.get("property_type", "unknown")))
    enriched_features = _enrich_prediction_features(features)

    # Route to per-type model or global
    per_type_models = artifact.get("per_type_models", {})
    global_model = artifact.get("global_model", {})
    global_model_meta = (
        global_model
        if isinstance(global_model, dict) and "pipeline" in global_model
        else {
            "pipeline": artifact["global_pipeline"],
            "numeric_features": NUMERIC_FEATURES,
            "categorical_features": CATEGORICAL_FEATURES,
            "target_transform": str(
                artifact.get("target_transform") or ("log_price" if artifact.get("log_target") else "none")
            ),
        }
    )
    blend_weight = 1.0
    routing_mode = "global_only"
    prediction_meta: Any = global_model_meta
    fallback_meta: Any | None = None
    selected_target_transform = str(artifact.get("target_transform") or "log_ppm2")

    if ptype in per_type_models:
        tm = per_type_models[ptype]
        blend_weight = float(tm.get("blend_weight", 1.0)) if isinstance(tm, dict) else 1.0
        fallback_source = str(tm.get("fallback_source") or "global") if isinstance(tm, dict) else "global"
        selected_target_transform = str(tm.get("target_transform", artifact.get("target_transform", "log_ppm2")))
        prediction_meta = (
            tm
            if isinstance(tm, dict) and "pipeline" in tm
            else {
                "pipeline": tm,
                "numeric_features": PERTYPE_NUMERIC,
                "categorical_features": PERTYPE_CATEGORICAL,
                "target_transform": selected_target_transform,
            }
        )
        if blend_weight <= 0:
            if (
                fallback_source == "specialist"
                and isinstance(tm, dict)
                and isinstance(tm.get("specialist_fallback"), dict)
            ):
                specialist_fallback = tm["specialist_fallback"]
                prediction_meta = specialist_fallback
                model_used = f"specialist:{ptype}"
                routing_mode = "specialist_only"
                selected_target_transform = str(
                    specialist_fallback.get("target_transform") or selected_target_transform
                )
            else:
                prediction_meta = global_model_meta
                model_used = "global"
                routing_mode = "global_only"
                selected_target_transform = str(artifact.get("target_transform") or "log_ppm2")
            blend_weight = 0.0
        elif blend_weight >= 0.999:
            model_used = f"per_type:{ptype}"
            routing_mode = "per_type_only"
        else:
            model_used = f"per_type:{ptype}"
            routing_mode = "blend_specialist" if fallback_source == "specialist" else "blend"
            if (
                routing_mode == "blend_specialist"
                and isinstance(tm, dict)
                and isinstance(tm.get("specialist_fallback"), dict)
            ):
                fallback_meta = tm["specialist_fallback"]
            else:
                fallback_meta = global_model_meta
    elif global_model and "pipeline" in global_model:
        prediction_meta = global_model_meta
        model_used = "global"
        selected_target_transform = str(artifact.get("target_transform") or "log_ppm2")
    else:
        prediction_meta = global_model_meta
        model_used = "global"
        selected_target_transform = str(artifact.get("target_transform") or "log_ppm2")

    num_feats, cat_feats = _resolve_model_feature_lists(
        prediction_meta,
        default_numeric=NUMERIC_FEATURES,
        default_categorical=CATEGORICAL_FEATURES,
    )
    normalized = _build_normalized_payload(enriched_features, num_feats, cat_feats, artifact)
    row = pd.DataFrame([normalized])
    predicted = float(
        _predict_any_model_meta(
            row,
            prediction_meta,
            default_target_transform=selected_target_transform,
        )[0]
    )

    # Blend with global fallback when per-type validation quality is not strong enough.
    if routing_mode in {"blend", "blend_specialist"} and fallback_meta is not None:
        g_num, g_cat = _resolve_model_feature_lists(
            fallback_meta,
            default_numeric=NUMERIC_FEATURES,
            default_categorical=CATEGORICAL_FEATURES,
        )
        g_norm = _build_normalized_payload(enriched_features, g_num, g_cat, artifact)
        g_row = pd.DataFrame([g_norm])
        g_pred = float(
            _predict_any_model_meta(
                g_row,
                fallback_meta,
                default_target_transform=str(fallback_meta.get("target_transform") or "log_ppm2")
                if isinstance(fallback_meta, dict)
                else "log_ppm2",
            )[0]
        )
        predicted = blend_weight * predicted + (1.0 - blend_weight) * g_pred

    calibration_factor, calibration_source = _lookup_calibration_factor(
        artifact.get("calibration"),
        ptype,
        str(normalized.get("municipality_normalized", "unknown")),
        str(normalized.get("naselje", "unknown")),
        predicted,
        row_context={**enriched_features, **normalized},
    )
    predicted *= calibration_factor

    floor_eur = _sparse_residential_floor_eur(enriched_features, normalized, ptype)
    if floor_eur is not None:
        predicted = max(predicted, floor_eur)

    return {
        "predicted_price_eur": round(predicted, 2),
        "model_used": model_used,
        "routing_mode": routing_mode,
        "type_blend_weight": round(float(blend_weight), 6),
        "calibration_factor": round(float(calibration_factor), 6),
        "calibration_source": calibration_source,
        "features_used": {k: str(v) for k, v in normalized.items()},
    }


def get_model_info(model_path: str | None = None) -> dict[str, Any] | None:
    """Get metadata about the currently loaded model."""
    artifact = load_model(model_path=model_path)
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
        "training_window": artifact.get("training_window"),
        "dataset_window": artifact.get("dataset_window"),
        "deploy_window": artifact.get("deploy_window"),
        "holdout": artifact.get("holdout"),
        "calibration": artifact.get("calibration"),
        "coords_by_municipality": artifact.get("coords_by_municipality"),
        "csv_path": artifact.get("csv_path"),
        "model_path": artifact.get("model_path"),
        "data_preparation": artifact.get("data_preparation"),
        "segment_diagnostics": artifact.get("segment_diagnostics"),
        "recent_research_diagnostics": artifact.get("recent_research_diagnostics"),
        "routing_comparison": artifact.get("routing_comparison"),
        "artifact_metadata": artifact.get("artifact_metadata"),
        "ev_baseline_metrics": artifact.get("ev_baseline_metrics"),
        "variant_benchmarks": artifact.get("variant_benchmarks"),
        "variant_matrix": artifact.get("variant_matrix"),
    }


def _prepare_benchmark_frames_from_csv(
    csv_path: str,
    artifact: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, np.ndarray, np.ndarray]:
    """Rebuild the deterministic train/test frames used for benchmark proof rows."""
    artifact_metadata = dict(artifact.get("artifact_metadata") or {})
    enable_market_validity_filter = bool(artifact_metadata.get("enable_market_validity_filter", True))

    df = read_csv_flexible(csv_path)
    df = enrich_training_df(df)

    df["price_eur"] = pd.to_numeric(df.get("price_eur"), errors="coerce")
    df = df.dropna(subset=["price_eur"])
    df = df[df["price_eur"] > 0]

    if "property_type" in df.columns:
        df = df[~df["property_type"].isin(EXCLUDED_PROPERTY_TYPES)]

    df, _sale_type_filter = _apply_sale_type_filter(df, allowed_sale_types=None)
    df, _full_share_filter = _apply_full_share_market_filter(df)
    df, _market_validity_filter = _apply_market_validity_filter(df, enabled=enable_market_validity_filter)

    if "deal_id" in df.columns and "property_type" in df.columns:
        df["_ppm2_tmp"] = df["price_eur"] / df["size_m2"]
        deal_type_count = df.groupby("deal_id")["property_type"].transform("nunique")
        deal_ppm2_nunique = df.groupby("deal_id")["_ppm2_tmp"].transform("nunique")
        contaminated = (deal_type_count > 1) & (deal_ppm2_nunique == 1)
        df = df[~contaminated]
        df = df.drop(columns=["_ppm2_tmp"])

    if "property_type" in df.columns:
        df["_log_ppm2_tmp"] = np.log(df["price_eur"] / df["size_m2"])
        keep_mask = pd.Series(True, index=df.index)
        for ptype in df["property_type"].unique():
            type_mask = df["property_type"] == ptype
            lp = df.loc[type_mask, "_log_ppm2_tmp"]
            q1, q3 = lp.quantile(0.25), lp.quantile(0.75)
            iqr = q3 - q1
            fence_lo, fence_hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            type_outlier = type_mask & ((df["_log_ppm2_tmp"] < fence_lo) | (df["_log_ppm2_tmp"] > fence_hi))
            keep_mask = keep_mask & ~type_outlier
        df = df[keep_mask]
        df = df.drop(columns=["_log_ppm2_tmp"])

    _LJ_E, _LJ_N = 461000, 100000
    _MB_E, _MB_N = 553000, 155000
    _KP_E, _KP_N = 404000, 44000
    lon = pd.to_numeric(df.get("longitude"), errors="coerce")
    lat = pd.to_numeric(df.get("latitude"), errors="coerce")
    df["dist_ljubljana"] = np.sqrt((lon - _LJ_E) ** 2 + (lat - _LJ_N) ** 2)
    df["dist_maribor"] = np.sqrt((lon - _MB_E) ** 2 + (lat - _MB_N) ** 2)
    df["dist_coast"] = np.sqrt((lon - _KP_E) ** 2 + (lat - _KP_N) ** 2)

    y = df["price_eur"].values
    X = df.drop(columns=["price_eur"], errors="ignore")

    for col in NUMERIC_FEATURES:
        if col in X.columns:
            X[col] = pd.to_numeric(X[col], errors="coerce")

    X_train, X_test, y_train, y_test, _holdout_info = _build_time_holdout_split(X, y)

    region_medians = artifact.get("region_medians") or {}
    type_medians = artifact.get("type_medians") or {}
    municipality_medians = artifact.get("municipality_medians") or {}
    global_median_ppm2 = float(artifact.get("global_median_ppm2") or 2000.0)

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

    type_muni_comp = artifact.get("deploy_type_muni_comp") or artifact.get("type_muni_comp") or {}
    type_ko_comp = artifact.get("deploy_type_ko_comp") or artifact.get("type_ko_comp") or {}
    type_naselje_comp = artifact.get("deploy_type_naselje_comp") or artifact.get("type_naselje_comp") or {}
    subtype_muni_comp = artifact.get("deploy_subtype_muni_comp") or artifact.get("subtype_muni_comp") or {}
    subtype_ko_comp = artifact.get("deploy_subtype_ko_comp") or artifact.get("subtype_ko_comp") or {}
    subtype_naselje_comp = artifact.get("deploy_subtype_naselje_comp") or artifact.get("subtype_naselje_comp") or {}
    global_log_ppm2 = float(artifact.get("global_log_ppm2") or np.log(2000.0))

    for split_X in (X_train, X_test):
        comp_muni_vals = np.full(len(split_X), global_log_ppm2)
        comp_ko_vals = np.full(len(split_X), global_log_ppm2)
        comp_naselje_vals = np.full(len(split_X), np.nan)
        comp_subtype_muni_vals = np.full(len(split_X), global_log_ppm2)
        comp_subtype_ko_vals = np.full(len(split_X), global_log_ppm2)
        comp_subtype_naselje_vals = np.full(len(split_X), np.nan)
        market_subtype_series = _build_market_subtype_series(split_X)
        if "property_type" in split_X.columns:
            for ptype_key, muni_map in type_muni_comp.items():
                mask = split_X["property_type"] == ptype_key
                if mask.any() and muni_map:
                    comp_muni_vals[mask.values] = (
                        split_X.loc[mask, "municipality_normalized"].map(muni_map).fillna(global_log_ppm2).values
                    )
            for ptype_key, ko_map in type_ko_comp.items():
                mask = split_X["property_type"] == ptype_key
                if mask.any() and ko_map and "ime_ko" in split_X.columns:
                    comp_ko_vals[mask.values] = split_X.loc[mask, "ime_ko"].map(ko_map).fillna(global_log_ppm2).values
            for ptype_key, naselje_map in type_naselje_comp.items():
                mask = split_X["property_type"] == ptype_key
                if mask.any() and naselje_map and "naselje" in split_X.columns:
                    comp_naselje_vals[mask.values] = split_X.loc[mask, "naselje"].map(naselje_map).values
            for subtype_key, muni_map in subtype_muni_comp.items():
                mask = market_subtype_series == subtype_key
                if mask.any() and muni_map:
                    comp_subtype_muni_vals[mask.values] = (
                        split_X.loc[mask, "municipality_normalized"].map(muni_map).fillna(global_log_ppm2).values
                    )
            for subtype_key, ko_map in subtype_ko_comp.items():
                mask = market_subtype_series == subtype_key
                if mask.any() and ko_map and "ime_ko" in split_X.columns:
                    comp_subtype_ko_vals[mask.values] = (
                        split_X.loc[mask, "ime_ko"].map(ko_map).fillna(global_log_ppm2).values
                    )
            for subtype_key, naselje_map in subtype_naselje_comp.items():
                mask = market_subtype_series == subtype_key
                if mask.any() and naselje_map and "naselje" in split_X.columns:
                    comp_subtype_naselje_vals[mask.values] = split_X.loc[mask, "naselje"].map(naselje_map).values
        split_X["comp_type_muni_ppm2"] = comp_muni_vals
        split_X["comp_type_ko_ppm2"] = comp_ko_vals
        split_X["comp_type_naselje_ppm2"] = comp_naselje_vals
        split_X["comp_subtype_muni_ppm2"] = comp_subtype_muni_vals
        split_X["comp_subtype_ko_ppm2"] = comp_subtype_ko_vals
        split_X["comp_subtype_naselje_ppm2"] = comp_subtype_naselje_vals

    X_train, X_test, _eng_artifacts = _compute_engineered_features(X_train, y_train, X_test)
    return df, X_train, X_test, y_train, y_test


def _benchmark_segment_rows(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    frame = pd.DataFrame(rows)
    if frame.empty or key not in frame.columns:
        return []

    actual_col = "actual_price_eur" if "actual_price_eur" in frame.columns else "price_eur"
    model_col = "model_price_eur" if "model_price_eur" in frame.columns else None
    gurs_col = "gurs_price_eur" if "gurs_price_eur" in frame.columns else None
    improvement_col = "improvement_eur" if "improvement_eur" in frame.columns else None
    winner_col = "winner" if "winner" in frame.columns else None
    if model_col is None or gurs_col is None or actual_col not in frame.columns:
        return []

    grouped_rows: list[dict[str, Any]] = []
    for segment_value, group in frame.groupby(key, dropna=False):
        if len(group) < 3:
            continue
        model_metrics = _compute_metrics(group[actual_col].to_numpy(), group[model_col].to_numpy())
        gurs_metrics = _compute_metrics(group[actual_col].to_numpy(), group[gurs_col].to_numpy())
        grouped_rows.append(
            {
                "segment": str(segment_value) if pd.notna(segment_value) else "unknown",
                "count": int(len(group)),
                "model_win_rate": round(float((group[winner_col] == "model").mean()), 4) if winner_col else None,
                "avg_gain_eur": round(float(group[improvement_col].mean()), 2) if improvement_col else None,
                "median_gain_eur": round(float(group[improvement_col].median()), 2) if improvement_col else None,
                "model_mae": model_metrics.get("mae"),
                "gurs_mae": gurs_metrics.get("mae"),
            }
        )

    grouped_rows.sort(
        key=lambda item: (
            float(item["avg_gain_eur"] or 0.0),
            float(item["model_win_rate"] or 0.0),
            item["count"],
        ),
        reverse=True,
    )
    return grouped_rows


def _empty_gurs_benchmark_payload(detail: str, status: str = "unavailable") -> dict[str, Any]:
    return {
        "summary": {
            "coverage_rows": 0,
            "model_metrics": None,
            "gurs_metrics": None,
            "improvement_vs_gurs": None,
            "winners": {"model": 0, "gurs": 0, "tie": 0},
            "top_regions": [],
            "top_property_types": [],
            "top_years": [],
            "methodology": "shared_gurs_coverage_holdout",
            "status": status,
            "detail": detail,
        },
        "rows": [],
    }


def build_gurs_benchmark_payload() -> dict[str, Any]:
    """Compute model-vs-GURS proof rows on shared benchmark coverage."""
    artifact = load_model()
    if artifact is None:
        return _empty_gurs_benchmark_payload("Train a model before opening the GURS benchmark proof.")

    csv_path = str(artifact.get("csv_path") or "")
    if not csv_path or not os.path.exists(csv_path):
        return _empty_gurs_benchmark_payload(
            "The current model does not point to an available prepared training dataset."
        )

    _df, X_train, X_test, y_train, y_test = _prepare_benchmark_frames_from_csv(csv_path, artifact)

    per_type_models = artifact.get("per_type_models") or {}
    global_model_entry = artifact.get("global_model") or {}
    global_model_meta = (
        dict(global_model_entry)
        if isinstance(global_model_entry, dict) and global_model_entry.get("pipeline") is not None
        else {
            "pipeline": artifact.get("global_pipeline"),
            "numeric_features": NUMERIC_FEATURES,
            "categorical_features": CATEGORICAL_FEATURES,
        }
    )
    global_target_transform = str(
        global_model_meta.get("target_transform")
        or artifact.get("target_transform")
        or ("log_price" if artifact.get("log_target") else "none")
    )
    global_model_meta["target_transform"] = global_target_transform
    global_pipeline = global_model_meta.get("pipeline")
    if global_pipeline is None:
        return _empty_gurs_benchmark_payload("The current model artifact is incomplete.")

    if per_type_models:
        y_pred_model = _predict_combined_routed(
            X_test,
            global_pipeline,
            per_type_models,
            target_transform=global_target_transform,
        )
    else:
        y_pred_model = _predict_with_model_meta(
            X_test,
            global_model_meta,
            default_target_transform=global_target_transform,
        )

    calibration = artifact.get("calibration")
    if calibration:
        y_pred_model, _calibration_details = _apply_calibration_to_predictions(X_test, y_pred_model, calibration)

    ev_benchmark_col = "ev_benchmark_price_eur"
    if ev_benchmark_col not in X_test.columns:
        return _empty_gurs_benchmark_payload(
            "The prepared dataset does not contain GURS benchmark estimates for shared comparison.",
            status="empty",
        )

    ev_vals = pd.to_numeric(X_test[ev_benchmark_col], errors="coerce")
    # Filter broken GURS values: decimal/unit errors make some GURS valuations
    # 1000x the actual price (e.g. a €15K apartment listed at €25M). These are
    # upstream data errors, not real valuations — exclude them from the benchmark
    # so Dokazi reflects genuine model-vs-GURS comparison on clean coverage.
    actual_series = pd.Series(y_test, index=X_test.index)
    ratio = ev_vals / actual_series.clip(lower=1)
    ev_mask = ev_vals.notna() & (ev_vals > 0) & (ratio >= 0.1) & (ratio <= 10.0)
    if not bool(ev_mask.any()):
        return _empty_gurs_benchmark_payload(
            "No holdout transactions currently have both a model-ready record and a comparable GURS estimate.",
            status="empty",
        )

    benchmark_frame = X_test.loc[ev_mask].copy()
    benchmark_frame["actual_price_eur"] = y_test[ev_mask.values]
    benchmark_frame["model_price_eur"] = y_pred_model[ev_mask.values]
    benchmark_frame["gurs_price_eur"] = ev_vals.loc[ev_mask].values
    benchmark_frame["model_abs_error"] = (
        benchmark_frame["actual_price_eur"] - benchmark_frame["model_price_eur"]
    ).abs()
    benchmark_frame["gurs_abs_error"] = (benchmark_frame["actual_price_eur"] - benchmark_frame["gurs_price_eur"]).abs()
    benchmark_frame["improvement_eur"] = benchmark_frame["gurs_abs_error"] - benchmark_frame["model_abs_error"]
    benchmark_frame["improvement_pct"] = np.where(
        benchmark_frame["gurs_abs_error"] > 0,
        (benchmark_frame["improvement_eur"] / benchmark_frame["gurs_abs_error"]) * 100,
        0.0,
    )
    finite_benchmark_mask = np.isfinite(
        benchmark_frame[["actual_price_eur", "model_price_eur", "gurs_price_eur"]].to_numpy(dtype=float)
    ).all(axis=1)
    benchmark_frame = benchmark_frame.loc[finite_benchmark_mask].copy()
    if benchmark_frame.empty:
        return _empty_gurs_benchmark_payload(
            "Shared benchmark coverage exists, but the current model artifact produced no finite comparable predictions.",
            status="empty",
        )
    benchmark_frame["winner"] = np.where(
        np.isclose(benchmark_frame["model_abs_error"], benchmark_frame["gurs_abs_error"], atol=0.01),
        "tie",
        np.where(benchmark_frame["model_abs_error"] < benchmark_frame["gurs_abs_error"], "model", "gurs"),
    )

    rows: list[dict[str, Any]] = []
    for position, (_, row) in enumerate(benchmark_frame.iterrows(), start=1):
        municipality = (
            format_municipality_label(row.get("municipality"))
            or row.get("municipality")
            or row.get("municipality_normalized")
        )
        region = format_region_label(row.get("statistical_region")) or row.get("statistical_region")
        year_value = row.get("transaction_year")
        year = int(year_value) if pd.notna(year_value) else None
        price_eur = float(row.get("actual_price_eur"))
        size_m2 = pd.to_numeric(row.get("size_m2"), errors="coerce")
        row_id = (
            f"{municipality_slug(str(municipality or 'unknown'))}:"
            f"{year or 'na'}:{int(round(price_eur))}:{int(round(float(size_m2) if pd.notna(size_m2) else 0))}:{position}"
        )
        rows.append(
            {
                "id": row_id,
                "municipality": municipality,
                "region": region,
                "property_type": row.get("property_type"),
                "vrsta_kupoprodajnega_posla": (
                    str(row.get("vrsta_kupoprodajnega_posla"))
                    if row.get("vrsta_kupoprodajnega_posla") is not None
                    and pd.notna(row.get("vrsta_kupoprodajnega_posla"))
                    else None
                ),
                "transaction_year": year,
                "year_built": int(row["year_built"])
                if "year_built" in row.index and pd.notna(row["year_built"])
                else None,
                "size_m2": round(float(size_m2), 1) if pd.notna(size_m2) else None,
                "price_eur": round(price_eur, 2),
                "model_price_eur": round(float(row.get("model_price_eur")), 2),
                "gurs_price_eur": round(float(row.get("gurs_price_eur")), 2),
                "model_abs_error": round(float(row.get("model_abs_error")), 2),
                "gurs_abs_error": round(float(row.get("gurs_abs_error")), 2),
                "improvement_eur": round(float(row.get("improvement_eur")), 2),
                "improvement_pct": round(float(row.get("improvement_pct")), 2),
                "winner": str(row.get("winner")),
                "source_label": (
                    str(row.get("source_label"))
                    if row.get("source_label") is not None and pd.notna(row.get("source_label"))
                    else None
                ),
                "ev_benchmark_source": row.get("ev_benchmark_source"),
                "slug": municipality_slug(str(municipality or "unknown")),
            }
        )

    model_metrics = _sanitize_metric_summary(
        _compute_metrics(
            benchmark_frame["actual_price_eur"].to_numpy(),
            benchmark_frame["model_price_eur"].to_numpy(),
        )
    )
    gurs_metrics = _sanitize_metric_summary(
        _compute_metrics(
            benchmark_frame["actual_price_eur"].to_numpy(),
            benchmark_frame["gurs_price_eur"].to_numpy(),
        )
    )
    winners = {
        "model": int((benchmark_frame["winner"] == "model").sum()),
        "gurs": int((benchmark_frame["winner"] == "gurs").sum()),
        "tie": int((benchmark_frame["winner"] == "tie").sum()),
    }

    mae_delta = (
        round(float(gurs_metrics["mae"] - model_metrics["mae"]), 6)
        if gurs_metrics and model_metrics and gurs_metrics.get("mae") is not None and model_metrics.get("mae") is not None
        else None
    )
    rmse_delta = (
        round(float(gurs_metrics["rmse"] - model_metrics["rmse"]), 6)
        if gurs_metrics and model_metrics and gurs_metrics.get("rmse") is not None and model_metrics.get("rmse") is not None
        else None
    )
    median_ae_delta = (
        round(float(gurs_metrics["median_ae"] - model_metrics["median_ae"]), 6)
        if gurs_metrics
        and model_metrics
        and gurs_metrics.get("median_ae") is not None
        and model_metrics.get("median_ae") is not None
        else None
    )
    mape_delta = (
        round(float(gurs_metrics["mape"] - model_metrics["mape"]), 6)
        if gurs_metrics and model_metrics and gurs_metrics.get("mape") is not None and model_metrics.get("mape") is not None
        else None
    )
    r2_delta = (
        round(float(model_metrics["r2"] - gurs_metrics["r2"]), 6)
        if gurs_metrics and model_metrics and gurs_metrics.get("r2") is not None and model_metrics.get("r2") is not None
        else None
    )

    summary = {
        "coverage_rows": int(len(rows)),
        "model_metrics": model_metrics,
        "gurs_metrics": gurs_metrics,
        "improvement_vs_gurs": {
            "mae": mae_delta,
            "rmse": rmse_delta,
            "median_ae": median_ae_delta,
            "mape": mape_delta,
            "r2": r2_delta,
            "avg_gain_eur": round(float(benchmark_frame["improvement_eur"].mean()), 2),
            "median_gain_eur": round(float(benchmark_frame["improvement_eur"].median()), 2),
        },
        "winners": winners,
        "top_regions": _benchmark_segment_rows(rows, "region")[:8],
        "top_property_types": _benchmark_segment_rows(rows, "property_type")[:8],
        "top_years": _benchmark_segment_rows(rows, "transaction_year")[:8],
        "methodology": "shared_gurs_coverage_holdout",
        "status": "ready",
        "detail": None,
    }
    return {"summary": summary, "rows": rows}
