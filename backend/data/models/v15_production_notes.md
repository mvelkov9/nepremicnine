# v15 Production Notes

This document summarizes the code-backed changes shipped with the v15 production
training launcher, [`backend/scripts/run_v15_production_train.py`](../../scripts/run_v15_production_train.py).
It does not claim fresh holdout metrics; retrain the model and inspect
`data/models/train_summary_latest.json` for run-specific results.

## Scope

- Dataset window: `2020-2026`
- Sale type filter: `{1}` (open-market sales)
- Variant label: `v15_production`
- Benchmark search variants: disabled in the launcher

## Changes Included in v15

1. **Tighter market-validity thresholds** for production filtering:
   - `stanovanje`: `min_price_eur=8000`, `min_ppm2=500`
   - `hisa`: `min_price_eur=15000`, `min_ppm2=250`
   - `parcela`: `min_price_eur=2500`, `min_ppm2=0.45`
   - `garaza`: `min_price_eur=6000`, `min_ppm2=300`
   - `poslovni_prostor`: `min_price_eur=10000`, `min_ppm2=250`
   - `industrijski`: `min_price_eur=8000`, `min_ppm2=100`
   - `turisticni` / `gostinstvo`: `min_price_eur=10000`, `min_ppm2=200`
   - `kmetijsko`: `min_price_eur=5000`, `min_ppm2=70`, plus unknown-municipality drop
2. **Stronger recency weighting** in training samples. The weighting is now exponential and scaled to a 4:1 recent-to-old ratio across the observed year range.
3. **Tighter per-municipality outlier removal**. Transactions are removed when `log(ppm2)` is more than 2.0 standard deviations away from the local `(property_type, municipality)` mean, with a minimum group size of 20.
4. **Large-type hyperparameter preservation after GPU adjustments**. For `stanovanje`, `hisa`, and `parcela`, explicit overrides for iterations, learning rate, depth, and `od_wait` are re-applied after GPU-safe parameter rewriting so the intended large-fit settings survive.
5. **Lossguide leaf budget increase** for large GPU fits. When Lossguide is enabled, `max_leaves` is now `128`.
6. **Market-validity filtering is always enabled** for training and benchmark-frame reconstruction unless explicitly overridden in artifact metadata.

## Important Stability Decision

`RMSE` remains the production loss. Earlier experiment notes in `optimized_v1_results.md`
and `optimized_v3_results.md` documented two reasons for not promoting Huber:

- Huber, MAE, and Quantile were unstable on CatBoost GPU in the surrounding runs.
- Even when Huber trained, holdout quality regressed relative to the stable RMSE setup.

That is why the v15 launcher documents the stricter filtering and weighting changes, but
keeps the production loss on `RMSE`.
