# Phase 3: ML Pipeline

**Status:** ✅ Complete  
**Commit:** `1b227cb`

## Checklist

- [x] ETN data processing (CSV parsing, pair detection, feature extraction)
- [x] Per-type HistGradientBoostingRegressor architecture (8 property types + global fallback)
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
| `app/services/model_service.py` | Per-type HistGBR training, prediction, model serialization (joblib) |
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
       └─ Filter data → Feature engineering → HistGradientBoostingRegressor
       └─ Save metrics (R², MAE) to model_runs table
    └─ Serialize all models → models/price_model.joblib

Prediction Pipeline:
  User input → Load model artifact → Select type-specific model
    → Prepare features → Predict → Log to prediction_logs table
```

## Model Details

- **Algorithm:** `HistGradientBoostingRegressor` (scikit-learn)
- **Architecture:** Separate model per property type + global fallback (v7.1)
- **Target transform:** log(price/m²) — model predicts log unit price, multiplied by size at prediction
- **Data cleaning:** Mixed-type deal contamination removal (pro-rated prices from bundled deals where garage gets apartment ppm2, etc.)
- **Feature selection:** Signal-scored per-type (Spearman correlation for numeric, target-mean for categorical), with type-specific "always include" sets
- **Features (core):** size_m2, rooms, year_built, floor, building_age, municipality (TargetEncoded), statistical_region, latitude, longitude, log_size_m2, transaction_year, transaction_quarter, price_per_m2_region, price_per_m2_municipality, price_per_m2_type
- **Features (spatial):** dist_ljubljana, dist_maribor, dist_coast (Euclidean distance in meters from ETRS89/TM coordinates)
- **Features (comparable sales):** comp_type_muni_ppm2, comp_type_ko_ppm2 (median log(ppm2) per type+municipality and type+cadastral_community from training data)
- **Features (amenities):** has_garaza, has_klet, has_shramba, has_terasa, has_parking, novogradnja, stavba_je_dokoncana, ddv_vkljucen, lega_v_stavbi, vrsta_kupoprodajnega_posla, vrsta_zemljisca
- **Features (EV register):** ev_ima_dvigalo, ev_ima_vodovod, ev_ima_kanalizacijo, ev_ima_elektriko, ev_ima_plin, ev_st_etaz, ev_del_st_nadstropja, ev_del_povrsina, ev_del_upor_pov, ev_leto_izg_stavbe, ev_id_lega, ev_id_dr_dst, ev_id_tip_stavbe, ev_leto_obn_strehe, ev_leto_obn_fasade, ev_leto_obn_oken, ev_leto_obn_inst, ev_parcela_povrsina, ev_boniteta
- **Features (GJI infrastructure):** gji_vodovod_distance_m, gji_vodovod_nearby_100m, gji_kanalizacija_distance_m, gji_kanalizacija_nearby_100m
- **Features (EMV valuation zones):** emv_zone_level, emv_zone_id
- **Features (KN/RN):** kn_ggo_openness, rn_address_match
- **Hyperparameters:** Adaptive by dataset size — 6 tiers (max_iter, learning_rate, max_depth, min_samples_leaf, l2_regularization)
- **Per-type outlier clipping:** P1–P99 for large types (>5000), P2–P98 for smaller
- **Metrics tracked:** R², MAE, RMSE, MAPE, median_ae per property type
- **EV Benchmark:** GURS POSPLOSENA_VREDNOST used as benchmark only (not a training feature) — model must beat government valuation
- **Variant benchmarking:** Automatic A/B comparison of etn_only vs deterministic vs full enrichment
- **Serialization:** joblib → `models/price_model.joblib`

## GURS Data Integration

The system joins multiple GURS datasets to enrich ETN transaction data:

| Source | Join Key | Features Added |
|--------|----------|---------------|
| EV stavba (buildings) | SIFRA_KO + STEVILKA_STAVBE | construction year, num floors, material, utilities, building type |
| EV del_stavbe (building parts) | SIFRA_KO + STEVILKA_STAVBE + STEVILKA_DELA_STAVBE | floor number, area, elevator, position, renovation years |
| EV del_stavbe_enota (valuation) | EID_DEL_STAVBE | POSPLOSENA_VREDNOST (benchmark only) |
| EV parcela (parcels) | SIFRA_KO + PARCELNA_STEVILKA | parcel area, boniteta, openness |
| RN (address register) | obcina + naselje + ulica + hisna_stevilka | precise coordinates, region IDs |
| GJI vodovod/kanalizacija | spatial (nearest distance) | distance to water/sewage infrastructure |
| EMV vrednostne cone | spatial (point-in-polygon) | valuation zone level and ID |
| KN kat. obcine / GGO | spatial (point-in-polygon) | cadastral community, forest openness |

## Async Bulk Preparation

The bulk preparation pipeline (`prepare_training_csv_from_etn_kpp_bulk`) runs as an ARQ background task with real-time progress updates via Redis. It processes multiple ETN year pairs, enriches with all GURS registers, and merges into a single training CSV.
