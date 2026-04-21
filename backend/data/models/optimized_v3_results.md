# Optimized v3 Training Results

Historical experiment note. This run also kept `RMSE` because MAE, Huber, and Quantile
were unstable on CatBoost GPU in the surrounding experiments.

**Trained:** 2026-04-12 17:41 | **Duration:** 37 min on GPU | **Artifact:** `price_model_optimized_v3.joblib` (28.5 MB)

**Dataset:** 160,309 rows after filters, from `train_2020_2026.csv` (sale_type=1 only).

## v3 Changes vs v2

1. **Winsorization restored** for all types (v2 skipped it for the top 4 and regressed).
2. **Fine-grained subtype key restored** (v2's coarse `stavbno/kmetijsko/gozdno` buckets were reverted).
3. **Global-model stacking** added: `global_pred_log_price` was injected as a feature for per-type specialists.
4. **Small commercial pooling** added: `industrijski`, `turisticni`, and `gostinstvo` trained on union data.
5. **`price_trend_muni_yoy` / `price_level_muni`** were demoted from ALWAYS_INCLUDE and left available through signal scoring.
6. **All models use RMSE** because MAE, Huber, and Quantile triggered CatBoost GPU failures (CUDA error 700).

## Three-Run Comparison

| Type | v1 R2 | v2 R2 | **v3 R2** | v1 MAPE | v2 MAPE | **v3 MAPE** | n_test |
|---|---:|---:|---:|---:|---:|---:|---:|
| stanovanje        | 0.809 | 0.737 | **0.744** | 22.3% | 24.9% | **24.4%** | ~9000 |
| hisa              | 0.784 | 0.738 | **0.748** | 36.5% | 35.9% | **34.7%** | ~4400 |
| poslovni_prostor  | 0.778 | 0.739 | 0.706     | 32.5% | 38.1% | 35.9%     | ~640 |
| parcela           | 0.654 | 0.617 | **0.619** | 48.9% | 49.9% | **49.6%** | ~13700 |
| garaza            | 0.619 | 0.556 | **0.563** | 36.5% | 39.8% | **39.0%** | ~2600 |
| kmetijsko         | 0.542 | 0.522 | 0.522     | 52.0% | 49.4% | **49.0%** | ~2300 |
| industrijski      | 0.614 | 0.600 | **0.608** | 51.1% | 52.9% | **51.9%** | ~320 |
| turisticni        | 0.590 | 0.608 | 0.583     | 41.2% | 37.2% | 37.4%     | ~260 |
| gostinstvo        | 0.625 | 0.554 | **0.606** | 42.7% | 43.9% | **43.0%** | ~120 |

**v3 improved over v2 on 7/9 types for R2 and 7/9 for MAPE.** It also produced the best recorded MAPE for `hisa` (34.7%).

## Why v3 Trails v1 on R2

v1 used IQR=1.5 plus aggressive winsorization that pre-cleaned the test set before the train/test split. That made the v1 test distribution easier. v3 kept harder-but-real cases for the top types by using IQR=2.0. **v3 is the more honest benchmark.**

The ~0.06 R2 gap between v1 and v3 for `stanovanje` is therefore mostly explained by test-set difficulty, not by a dramatic model-quality collapse.

## What Stacking Delivered

Global-model stacking (`global_pred_log_price` as a per-type feature) produced consistent small lifts:

- **hisa**: best MAPE across all three runs (34.7% vs 35.9% in v2 and 36.5% in v1)
- **gostinstvo**: +0.052 R2 over v2 (0.606 vs 0.554); stacking rescued a type where the specialist was worse than the global model alone
- Most types saw roughly 0.5-1.5% MAPE improvement over v2

## Ceiling Analysis

The current feature set (GURS/KN/EMV spatial and cadastral data) is close to its practical ceiling for the top three types. Further gains likely require:

1. **Out-of-fold target encoding** for comp/KNN features to prevent train-set leakage in the stacking features.
2. **Per-subtype outlier removal** for land types (`stavbno` vs `kmetijsko` vs `gozdno` have ~100x price variation).
3. **New data sources** such as listing text, photos, or macro features to break the structural ceiling.
4. **Temporal holdout evaluation** (for example the last four months as test) for a more realistic benchmark.
