# Phase 3: ML Pipeline

**Status:** ✅ Complete  
**Commit:** `1b227cb`

## Checklist

- [x] ETN data processing (CSV parsing, pair detection, feature extraction)
- [x] Per-type CatBoostRegressor architecture (9 property types + global fallback)
- [x] ARQ async worker + Redis task queue for background training
- [x] Training endpoints: start, status, jobs list
- [x] Prediction endpoints: predict (with model loading + feature prep)
- [x] Model info endpoints: info, importance, diagnostics
- [x] Frontend: ModelView with training trigger, progress bar, metrics display
- [x] Frontend: PredictionView with property form + price result
- [x] Data processing service: bulk prepare from uploaded CSVs
- [x] SHA-256 deduplication on uploads (prevents re-import)

## Key Files

| File | Purpose |
|------|---------|
| `app/services/data_processing_service.py` | ETN CSV → cleaned DataFrame, pair detection, feature extraction |
| `app/services/model_service.py` | Per-type CatBoost training, prediction, model serialization (joblib) |
| `app/tasks/training_worker.py` | ARQ async worker: runs training in background, updates job status |
| `app/api/train.py` | `/api/train/start`, `/api/train/status/{id}`, `/api/train/jobs` |
| `app/api/predict.py` | `/api/predict` (POST), `/api/predict/history` |
| `app/api/model.py` | `/api/model/info`, `/api/model/importance` |
| `app/schemas/model.py` | Pydantic schemas for prediction input/output, model info |
| `src/views/ModelView.vue` | Training UI: trigger, progress bar, per-type metrics table |
| `src/views/PredictionView.vue` | Property form (type, size, rooms, year, location) → predicted price |

## ML Architecture

```
Training Pipeline:
  Upload CSVs → Prepare (ETN pairs) → Start Training Job → ARQ Worker
    └─ For each property type (stanovanje, hiša, poslovni, etc.):
       └─ Filter data → Feature engineering → CatBoostRegressor
       └─ Save metrics (R², MAE) to model_runs table
    └─ Serialize all models → models/price_model.joblib

Prediction Pipeline:
  User input → Load model artifact → Select type-specific model
    → Prepare features → Predict → Log to prediction_logs table
```

## Model Details

- **Algorithm:** `CatBoostRegressor` (catboost) — migrated from scikit-learn HistGradientBoostingRegressor in v11.0
- **Architecture:** Separate model per property type (9 types) + global fallback, with combined routing
- **CatBoostModel wrapper:** Lightweight class handling native categorical features via `catboost.Pool`, no TargetEncoder needed
- **Target transform:** log(price/m²) — model predicts log unit price, inverse-transformed at prediction
- **Data cleaning:** Mixed-type deal contamination removal + IQR-based outlier removal (2.5x global, 1.8-2.2x per-type)
- **Feature selection:** Signal-scored per-type (Spearman correlation for numeric, target-mean for categorical), with type-specific "always include" sets
- **Boosting strategy:** Plain boosting for large types (>2000 rows, fast), Ordered boosting for small types (<2000 rows, better generalisation)
- **Features (85 numeric + 9 categorical for global model):**
  - **Core:** size_m2, rooms, year_built, floor, building_age, log_size_m2, transaction_year, transaction_quarter, price_per_m2_region, price_per_m2_municipality, price_per_m2_type
  - **Categorical (native):** municipality_normalized, property_type, statistical_region, lega_v_stavbi, ime_ko, naselje, vrsta_zemljisca, vrsta_kupoprodajnega_posla, kn_ggo_section
  - **Spatial:** dist_ljubljana, dist_maribor, dist_coast (Euclidean from ETRS89/TM)
  - **KNN spatial:** knn_5_log_ppm2, knn_20_log_ppm2, knn_type_10_log_ppm2 (median log(ppm2) of nearest neighbours via KDTree)
  - **Comparable sales:** comp_type_muni_ppm2, comp_type_ko_ppm2 (median log(ppm2) per type+municipality/KO)
  - **Engineered:** ko_vs_muni_premium, muni_vs_region_premium, price_per_m2_ko, ko/muni/naselje_transaction_count, size_percentile, time_index, parcel_sold_fraction, has_ev_data, has_renovation_data, years_since_renovation
  - **Amenities:** has_garaza, has_klet, has_shramba, has_terasa, has_parking, novogradnja, stavba_je_dokoncana, ddv_vkljucen
  - **EV register:** 20+ features (construction, utilities, renovations, building envelope)
  - **GJI infrastructure:** 6 types × (distance_m + nearby_100m) + 4 × nearby_500m
  - **KN/RN:** kn_ggo_openness, rn_address_match
- **Hyperparameters:** Adaptive by dataset size — 6 tiers (iterations, learning_rate, depth, l2_leaf_reg, od_wait, max_ctr_complexity, boosting_type)
- **Per-type feature configs:** Each type gets optimised numeric/categorical "always include" sets; small types (<2000 rows) exclude high-cardinality categoricals (ime_ko, naselje) to prevent overfitting
- **Early stopping:** 10% validation split from training, od_wait 80-250 (higher for smaller datasets)
- **Metrics tracked:** R², MAE, RMSE, MAPE, median_ae per property type + per-region + combined routing
- **EV Benchmark:** GURS POSPLOSENA_VREDNOST used as benchmark only (not a training feature)
- **Variant benchmarking:** Global-only A/B comparison of etn_only vs deterministic vs full enrichment
- **Serialization:** joblib → `models/price_model.joblib`

### Latest Training Results (v11.0 CatBoost, ~54 min)

| Type | R² | MAPE | Rows | Notes |
|------|-----|------|------|-------|
| gostinstvo | 0.8880 | 37.9% | 445 | Ordered boosting, minimal features |
| stanovanje | 0.8859 | 20.2% | 35K | Largest apartment dataset |
| poslovni_prostor | 0.8721 | 27.4% | 2.9K | |
| hisa | 0.7866 | 45.4% | 17K | |
| parcela | 0.7456 | 48.6% | 77K | Largest overall, land-only |
| turisticni | 0.7368 | 38.6% | 1.1K | Ordered boosting |
| garaza | 0.6331 | 33.9% | 12.7K | |
| industrijski | 0.6021 | 48.3% | 1.2K | Ordered boosting |
| kmetijsko | 0.5911 | 61.6% | 10.9K | Agricultural — high variance |
| **Combined** | **0.8587** | **41.2%** | **199K** | Routed per-type predictions |

## GURS Data Integration

The system joins multiple GURS datasets to enrich ETN transaction data:

| Source | Join Key | Features Added |
|--------|----------|---------------|
| EV stavba (buildings) | SIFRA_KO + STEVILKA_STAVBE | construction year, num floors, material, utilities, building type |
| EV del_stavbe (building parts) | SIFRA_KO + STEVILKA_STAVBE + STEVILKA_DELA_STAVBE | floor number, area, elevator, position, renovation years |
| EV del_stavbe_enota (valuation) | EID_DEL_STAVBE | POSPLOSENA_VREDNOST (benchmark only) |
| EV parcela (parcels) | SIFRA_KO + PARCELNA_STEVILKA | parcel area, boniteta, openness |
| RN (address register) | obcina + naselje + ulica + hisna_stevilka | precise coordinates, region IDs |
| GJI (6 infrastructure types) | spatial (nearest distance) | distance + nearby count for vodovod, kanalizacija, elektrika, plin, ceste, toplota |
| EMV vrednostne cone | spatial (point-in-polygon) | valuation zone level and ID (benchmark only) |
| KN kat. obcine / GGO | spatial (point-in-polygon) | cadastral community, forest openness |

## Async Bulk Preparation

The bulk preparation pipeline (`prepare_training_csv_from_etn_kpp_bulk`) runs as an ARQ background task with real-time progress updates via Redis. It processes multiple ETN year pairs, enriches with all GURS registers, and merges into a single training CSV.
