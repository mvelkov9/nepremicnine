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
- **Architecture:** Separate model per property type + global fallback
- **Features:** size_m2, rooms, year_built, floor, municipality (encoded), has_garaza, has_klet, has_shramba, has_terasa, novogradnja
- **Metrics tracked:** R², MAE, MAPE per property type
- **Serialization:** joblib → `models/price_model.joblib`
- **Typical results:** Global R² ~0.77, stanovanje R² ~0.85
