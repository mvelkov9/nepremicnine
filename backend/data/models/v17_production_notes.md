# v17 Production Notes

This document summarizes the changes shipped with the v17 production training
launcher, [`backend/scripts/run_v15_production_train.py`](../../scripts/run_v15_production_train.py).
Retrain the model and inspect `data/models/train_summary_latest.json` for
run-specific holdout metrics.

## Scope

- Dataset window: `2020-2026`
- Sale type filter: `{1}` (open-market sales)
- Variant label: `v17_production`
- Benchmark search variants: disabled in the launcher

## Headline Results (vs v13 baseline)

| Type             | R² (v13 → v17)    | MAPE (v13 → v17)      | MAE change |
| ---------------- | ----------------- | --------------------- | ---------- |
| stanovanje       | 0.821 → **0.855** | 20.9% → **17.8%**     | **−€2,421** |
| hisa             | 0.791 → **0.802** | 35.7% → **31.6%**     | −€897       |
| industrijski     | 0.620 → **0.632** | 48.2% → **45.0%**     | −€7         |
| parcela          | 0.713 → **0.721** | 45.7% → **45.0%**     | −€346       |
| kmetijsko        | 0.532 → **0.549** | 50.9% → **49.1%**     | −£679       |
| poslovni_prostor | 0.808 → **0.792** | 28.7% → **26.0%**     | −€807       |
| **Combined**     | 0.858 → **0.872** | 36.9% → **35.3%**     | **−€1,262** |

## Changes Included in v16 / v17 (cumulative vs v15)

1. **Adaptive per-municipality outlier threshold.** Large types (n ≥ 3 000)
   keep the v15 tight z-score (`>2.0`, min group 20); small types (n < 3 000 —
   industrijski, turisticni, gostinstvo) revert to `>2.5` with min group 30.
   Fixes the v15 regression on small types caused by over-trimming scarce data.
2. **stanovanje `min_ppm2` raised 500 → 700.** Removes ~3 000 additional
   noisy or partial-sale transactions still slipping through at €500–700/m²
   (e.g. Kranj €538/m² among €2 800 medians). Combined with stronger recency
   weighting, this lifts the Kranj stanovanje prediction toward current
   market levels.
3. **`log_price` specialist target for `stanovanje` and `hisa`.** Captures
   the non-linear size-price relationship (a 100 m² apartment is not 2×
   a 50 m² apartment). `poslovni_prostor` was initially promoted to
   `log_price` but reverted after v16 showed a −0.03 R² regression.
4. **Per-type price-tier sample weighting.** Top-quartile properties get
   a 1.5× weight to reduce MAE on high-value transactions that dominate
   absolute error.
5. **Price-tier boost is scoped to per-type models only.** Applied globally
   it mixes €10 K garaza with €500 K hisa, making "top quartile" meaningless.
   Global model and OOF folds disable `apply_price_boost` so they recover
   from the v16 regression on the unrouted global metric.

## Dokazi (GURS benchmark) Fixes

1. **Filter broken GURS valuations.** GURS source data contains ~0.1 %
   records with decimal/unit errors (a €15 K apartment listed at €25 M,
   a 120 m² apartment at €50 M). The benchmark now excludes any row where
   the GURS value is outside `[0.1×, 10×]` of the actual sale price.
2. **Graceful handling of incomplete global artifacts.** The benchmark no
   longer raises `RuntimeError` when the global pipeline is missing; it
   returns an empty payload with a clear detail string.
3. **Cache TTL extended from 5 min to 24 h.** Rebuild reads the full CSV
   and runs predictions (~30–60 s), and the payload only changes on retrain.

## Deployment Notes

- Production uses **one uvicorn worker** (`docker-compose.prod.yml`).
  Two workers × (500 MB CSV + KDTree + prediction frames) exhausted the
  7.6 GB host; memory now sits at ≈3.3 GB.
- The benchmark file `train_2020_2026.csv` is stored as a symlink to
  `train.csv` inside the Docker data volume. This keeps the model's
  recorded `csv_path` resolvable on the production server.

## Important Stability Decisions

- `RMSE` remains the production loss. Huber, MAE, and Quantile regressed
  holdout quality on CatBoost GPU in earlier experiments and were reverted.
- `poslovni_prostor` uses `log_ppm2` in v17 after v16 showed `log_price`
  was a net regression for that type.
