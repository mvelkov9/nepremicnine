# Optimized v1 Training Results

Historical experiment note. This run is still useful as a benchmark reference, but the
production code keeps `RMSE` as the loss because Huber was unstable on CatBoost GPU in
these experiments.

**Trained:** 2026-04-10 13:09 | **Duration:** 97.6 min on GPU (vs 6-7h on CPU baseline) | **Artifact:** `price_model_optimized.joblib` (25 MB)

**Dataset:** 159,684 rows (127,143 train / 32,541 test) after filters, from `train_2020_2026.csv` (234,387 raw rows, sale_type=1 only).

## Overall

| Metric | Baseline (2026-04-05) | Optimized v1 | Delta |
|---|---:|---:|---:|
| Combined R2 | n/a (per-type only audit) | **0.8417** | n/a |
| Combined MAPE | n/a | **39.1%** | n/a |
| Global-only R2 (within-run) | n/a | 0.708 | n/a |
| Global-only MAPE | n/a | 51.5% | n/a |
| Per-type lift over global | n/a | **+0.134 R2 / -12.4% MAPE** | n/a |

The 0.134 R2 lift from per-type specialists confirms the blend-routing architecture is doing real work; the global model alone would be much worse.

## Per-Type Comparison vs Baseline

| Type | Base R2 | Opt R2 | Delta R2 | Base MAPE | Opt MAPE | Delta MAPE | n_test |
|---|---:|---:|---:|---:|---:|---:|---:|
| stanovanje        | 0.806 | 0.809 | +0.003 | 23.5% | **22.3%** | -1.2  |  8607 |
| hisa              | 0.768 | 0.784 | +0.015 | 49.8% | **36.5%** | **-13.3** |  4257 |
| poslovni_prostor  | 0.788 | 0.778 | -0.010 | 32.4% |  32.5%    | +0.1  |   637 |
| parcela           | 0.667 | 0.654 | -0.013 | 56.7% | **48.9%** | -7.8  | 13440 |
| gostinstvo        | 0.613 | 0.625 | +0.012 | 45.3% |  42.7%    | -2.6  |   118 |
| turisticni        | 0.608 | 0.590 | -0.018 | 46.5% |  41.2%    | -5.3  |   261 |
| industrijski      | 0.584 | 0.614 | **+0.030** | 59.6% | **51.1%** | -8.5  |   320 |
| garaza            | 0.540 | 0.619 | **+0.079** | 47.3% | **36.5%** | -10.8 |  2617 |
| kmetijsko         | 0.483 | 0.542 | **+0.059** | 80.6% | **52.0%** | **-28.6** |  2284 |

**R2 improved for 6 of 9 types.** **MAPE improved for 8 of 9 types.** The biggest wins all came on the weak bottom of the table (`garaza`, `kmetijsko`, `industrijski`), exactly where the baseline was worst.

## Target vs Reality

User target: R2 > 0.90, MAPE < 10% for **every** type.

| Type | R2 gap to 0.90 | MAPE gap to 10% |
|---|---:|---:|
| stanovanje        | -0.091 | -12.3 pp |
| hisa              | -0.116 | -26.5 pp |
| poslovni_prostor  | -0.122 | -22.5 pp |
| parcela           | -0.246 | -38.9 pp |
| gostinstvo        | -0.275 | -32.7 pp |
| garaza            | -0.281 | -26.5 pp |
| industrijski      | -0.286 | -41.1 pp |
| turisticni        | -0.310 | -31.2 pp |
| kmetijsko         | -0.358 | -42.0 pp |

**We are not there yet, and we will not get there by tuning CatBoost alone.** The ceiling of what is learnable from the current GURS/KN/EMV feature set has essentially been reached for the top three types (`stanovanje`, `hisa`, `poslovni_prostor`). For land types and small commercial segments the problem is a mix of inherent heterogeneity (orchard vs meadow vs building plot all lumped together) and tiny datasets (`gostinstvo` has 455 training rows).

## What the Candidate Search Actually Chose

Interesting picks from the per-type candidate search:

- **stanovanje** -> `rich` features, `log_ppm2`, `recent_6y_weighted`, blend=1.0 (specialist-only). Global blend was worse than pure specialist here.
- **hisa** -> `simple` features won over `rich`, blend=1.0. Fewer features generalize better for houses.
- **poslovni_prostor** -> `simple`, `log_price`, `recent_3y_weighted`, blend=0.85. Recent-3y reflects how fast the commercial market moves.
- **parcela** -> `rich` + `log_price` + `full_history` beat the `land_focus` variant. Candidate search chose blend=0.5 with specialist-fallback routing.
- **kmetijsko** -> `rich` + `log_price` + `full_history`, blend=0.9 with specialist-fallback. `land_focus` variant did not win.
- **gostinstvo** -> blend=0.2 only. The specialist is *worse* than the global model alone (`per_type` R2=0.477 vs global R2=0.617). Too little data (455 rows) to train a useful specialist.

## Root Cause Notes From This Run

Three issues discovered and fixed during this session:

1. **Huber loss on CatBoost GPU is broken** in the current combination. Global model survived it by luck but every per-type fit collapsed at `bestIteration=1` with a deterministic `bestTest=23.58068891`. Reverting to `loss_function: RMSE` restored normal convergence (smoke test confirmed the loss dropped from 1.24 to 0.495 over 5000 iterations on `parcela`).
2. **Target leakage**: `vrsta_kupoprodajnega_posla` was being used as both a filter and a feature. It was removed from all feature variants.
3. **Windows stdout encoding**: Unicode arrows in log messages were crashing the stdout handler with `UnicodeEncodeError`, polluting logs with tracebacks. The launcher now uses UTF-8 line-buffered stdout and ASCII-safe log text.

## Concrete Next Steps

### Tier 1 - Quick Wins (next run, 1-2h)

1. **Restore IQR=2.0 outlier multiplier for top types** (`stanovanje`, `poslovni_prostor`, `hisa`, `parcela`). The aggressive IQR=1.5 plus winsorization used in this run likely pushed `stanovanje` R2 down 0.003 and `poslovni_prostor` R2 down 0.010 by clipping hard examples the model still needed.
2. **Pin candidate search for `parcela` and `kmetijsko` to the known winners.** Those two searches burned about 70 minutes running ~15 fits each. Disabling them frees time for seed sweeps or ensembles on `stanovanje` / `hisa`.
3. **Re-enable the `hisa` `rich` variant.** `simple` won this round, but the gap was small and `rich` still has headroom.

### Tier 2 - New Signal (needs 1-2 days of work)

4. **Explicit subtype routing for `parcela` and `kmetijsko`.** Split on `vrsta_zemljisca` before training, not as a feature. Building land and agricultural land are fundamentally different markets and likely need separate specialists.
5. **Listing text / photo feature extraction** for condition and quality. The current features cannot separate a renovated 1985 apartment from a derelict 1985 apartment. That is the main `stanovanje` / `hisa` ceiling.
6. **Quarter-level price trend indices per municipality.** Real estate moves by quarter; the current `price_trend_muni` signal is annualized.

### Tier 3 - Data Collection (requires new pipelines)

7. **Merge the small commercial types** (`turisticni`, `gostinstvo`, `industrijski`) into one pooled "other commercial" model and calibrate per-type on top.
8. **Add macro features** such as EURIBOR, inflation, and mortgage rates at the time of sale.
9. **Add a photo-based quality rating** for listing condition. High impact for `stanovanje` / `hisa`, but a multi-week build.

## Realistic Next-Iteration Targets

| Type | Realistic R2 target | Realistic MAPE target |
|---|---:|---:|
| stanovanje        | 0.82 | 20% |
| poslovni_prostor  | 0.80 | 30% |
| hisa              | 0.80 | 32% |
| parcela           | 0.70 | 42% |
| garaza            | 0.65 | 33% |
| kmetijsko         | 0.58 | 45% |
| industrijski      | 0.65 | 45% |
| turisticni        | 0.62 | 38% |
| gostinstvo        | 0.63 | 40% |

Reaching R2 > 0.90 / MAPE < 10% across the board requires the Tier 2 feature work plus the Tier 3 data work. That is a multi-week project, not a single tuning run.
