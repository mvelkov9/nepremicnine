# Nepremičnine — Master Tracking

## Overview

Complete rebuild of the Slovenian real estate price prediction application — from diploma prototype to a production-grade, publicly deployed platform.

| Item | Value |
|------|-------|
| **Version** | 0.16.0 |
| **Repo** | [github.com/mvelkov9/nepremicnine](https://github.com/mvelkov9/nepremicnine) |
| **Backend** | FastAPI + Python 3.13 + PostgreSQL 17 + SQLAlchemy 2.x async |
| **Frontend** | Vue 3 Composition API + TypeScript + Pinia + VueUse + pnpm 9, Vite 8 |
| **Testing** | Backend: pytest (async) · Frontend: Vitest + Playwright E2E |
| **ML** | CatBoostRegressor (per-type + global, native categorical handling) |
| **Auth** | JWT (access 15 min + refresh 7 days, SecretStr passwords), admin/viewer roles |
| **i18n** | Slovenian (default) + English |
| **CI/CD** | GitHub Actions → GHCR → VPS (SSH), Trivy security scanning, Dependabot |
| **Monitoring** | Prometheus metrics (`/metrics`), structured JSON logging, correlation IDs |
| **Infra** | Docker Compose (dev + prod profiles), cloud VPS |

## Phase Progress

| Phase | Description | Status | Commit |
|-------|-------------|--------|--------|
| [Phase 0](PHASE_0_FOUNDATION.md) | Foundation — skeleton, Docker, CI | ✅ Complete | `914a4ca` |
| [Phase 1](PHASE_1_BACKEND.md) | Backend Core — ORM, auth, CRUD, tests | ✅ Complete | `7b0a80c` |
| [Phase 2](PHASE_2_FRONTEND.md) | Frontend Core — pages, charts, stores | ✅ Complete | `1def8db` |
| [Phase 3](PHASE_3_ML_PIPELINE.md) | ML Pipeline — training, prediction, ARQ | ✅ Complete | `1b227cb` |
| [Phase 4](PHASE_4_FEATURES.md) | Features — map, diagnostics, admin, i18n | ✅ Complete | `fc18742` |
| [Phase 5](PHASE_5_PRODUCTION.md) | Production — Docker, CI/CD, deploy | ✅ Complete | `153f140` |
| [Phase 6](PHASE_6_V030.md) | Security hardening, backend robustness, frontend accessibility, expanded tests | ✅ Complete | `(v0.3.1)` |
| [Phase 7](PHASE_7_V040_V080.md) | Security hardening, feature completeness, test expansion, UX polish | ✅ Complete | (latest commit) |
| [Phase 8–17](PHASE_8_14_PLAN.md) | v1→v2 gap fixes, feature parity, performance, security, UX, tests, docs | ✅ Complete | — |
| [Phase 18](PHASE_8_14_PLAN.md#phase-18--cache-coherency--phase-tracking-v0814) | Agency re-audit, cache coherency fixes, tracked execution plan | ✅ Complete | `3cf6248` |
| [Phase 19](PHASE_8_14_PLAN.md#phase-19--dashboard-property-type-parity-v0815) | Dashboard property-type parity and analytical lens controls | ✅ Complete | `fb4a786` |
| [Phase 20](PHASE_8_14_PLAN.md#phase-20--diagnostics-focus--locale-formatting-v0816) | Diagnostics focus workflow and locale-aware formatting polish | ✅ Complete | `4c58881` |
| Phase 21 | Market UX and training reliability reset: structured progress, map legend/drawer, PrimeVue admin/viewer polish | ✅ Complete | `22c90cf` |
| Phase 22 | Data quality, map UX, and PrimeVue modernization: canonical municipality coverage, direct portal links, centered map modal, cached analytics, admin quality summary | ✅ Complete | working tree |
| [Phase 23](PHASE_23_MODERNIZATION.md) | Architecture modernization: TypeScript, VueUse, Vitest, Playwright E2E, DB optimization, API security hardening, performance benchmarking, accessibility audit, CI/CD overhaul, Prometheus monitoring | ✅ Complete | working tree |
| [Phase 24](PHASE_24_REDESIGN.md) | Full frontend redesign: PrimeVue component migration, layout decomposition, dark mode fixes, CSS cleanup | ✅ Complete | working tree |
| [Phase 25](PHASE_25_PRODUCT_RESET.md) | Product UX reset: benchmark proof workflow, server-side admin/data tables, workspace cleanup, shared reference caching | ✅ Complete | working tree |
| Phase 26 | ML v6–v9 training iterations: GPU training, ev_benchmark removal, per-type feature correlation audit, sub-segmentation infrastructure, v9 model deployment | ✅ Complete | working tree |

## Changelog

### v0.16.0

- **ML: Model v9 — correlation-based feature audit + sub-segmentation**: Comprehensive v8→v9 training iteration using GPU (71 min, 1 GPU, 158 976 rows)
- **ML: Feature restoration**: v8 pruned features using CatBoost importance alone, which conflated redundancy with lack of signal. v9 re-added all features with Spearman |r| ≥ 0.15 against log(€/m²). Biggest miss was parcela where ALL `gji_*_nearby_100m` had r = 0.44–0.66 but were excluded. Net gains: industrijski +3.5 R² pts, poslovni_prostor +1.6 R² pts.
- **ML: Sub-segmentation infrastructure**: Extended `_market_subtype_key_from_values` and `_build_market_subtype_series` to support garaza (by `vrsta_dela_stavbe` → aboveground/underground, ~50/50 split, 117pp spread) and hisa (by `ev_id_konstrukcija` → brick/concrete/wood/mixed/prefab, 81pp spread). Added both to `TYPE_SPECIALIST_MODEL_PRIORS` with `enable_subtype_family: True`. Finding: sub-models were not selected over parent per-type models because CatBoost already captures these splits via the feature itself — splitting data only hurts via sample size.
- **ML: New features**: Added `gji_zeleznice_nearby_100m` (r = 0.12–0.24, stronger than 1000m variant) and `ev_id_konstrukcija` (r = +0.165 on stanovanje) to `NUMERIC_FEATURES`.
- **ML: Analysis tooling**: Added `backend/scripts/full_correlation_analysis.py` (Spearman audit against all 129 CSV cols), `check_subsegment_viability.py` (fill rates, bucket counts, price spreads), `analyze_v7_feature_importance.py` (CatBoost gain extraction), `run_optimized_train.py` (GPU training launcher).
- **ML: v9 results** (routed, 2020–2026, GPU):
  | Type | v8 R² | v9 R² | Δ R² | v8 MAPE | v9 MAPE |
  |------|-------|-------|------|---------|---------|
  | stanovanje | 0.753 | 0.753 | 0.000 | 24.2% | 24.3% |
  | hisa | 0.743 | 0.747 | +0.004 | 34.8% | 34.9% |
  | poslovni_prostor | 0.694 | 0.710 | **+0.016** | 35.9% | 35.5% |
  | parcela | 0.699 | 0.698 | -0.001 | 46.1% | 45.8% |
  | garaza | 0.569 | 0.561 | -0.007 | 39.5% | 40.3% |
  | kmetijsko | 0.520 | 0.514 | -0.006 | 50.3% | 50.7% |
  | industrijski | 0.564 | 0.599 | **+0.035** | 52.7% | 52.8% |
  | turisticni | 0.618 | 0.617 | 0.000 | 36.1% | 36.1% |
  | gostinstvo | 0.539 | 0.541 | +0.002 | 40.5% | 40.6% |
- **Version**: 0.15.0 → 0.16.0

### v0.15.0

- **Proof workflow**: Added dedicated viewer and admin benchmark routes (`/dokaz`, `/admin/dokaz`) backed by new GURS comparison endpoints so the app can show where the model beats GURS on shared holdout coverage, by how much, and on which transactions
- **Server-side tables**: Standardized benchmark transactions, admin users, and the dataset library around route-synced server pagination, sorting, search, export, and filter state
- **Performance**: Added shared reference-data caching across key viewer pages, stale-request cancellation for stats explorers, and removed wasteful full-list fetches from admin summary screens
- **Frontend modernization**: Replaced remaining legacy `TabView` usage in the main explorer pages with PrimeVue `Tabs`, improved global tabs/table/focus styling, and refreshed the login/product shell
- **Navigation cleanup**: Demoted `Ukazi`, `Pladenj`, and `Aktivnosti` into a cleaner workspace entry while making the new proof workflow discoverable from dashboard, diagnostics, and admin navigation
- **Version**: 0.14.0 -> 0.15.0

### v0.14.0

- **ML: CatBoost migration**: Replaced scikit-learn HistGradientBoostingRegressor with CatBoostRegressor — native categorical handling (no TargetEncoder), built-in NaN support, early stopping with overfitting detector
- **ML: Adaptive boosting strategy**: Plain boosting for large types (>2000 rows, 2-3x faster), Ordered boosting for small types (<2000 rows, better generalisation on gostinstvo/turisticni/industrijski)
- **ML: Per-type feature optimisation**: Small types (<2000 rows) exclude high-cardinality categoricals (ime_ko ~2600, naselje ~5000) to prevent overfitting; gostinstvo trimmed from 38→13 always-include numeric features
- **ML: KNN spatial features**: knn_5_log_ppm2, knn_20_log_ppm2, knn_type_10_log_ppm2 added to all per-type models via _SPATIAL_ALWAYS set; ko_vs_muni_premium, muni_vs_region_premium, price_per_m2_ko added
- **ML: GJI infrastructure enrichment**: 6 infrastructure types (vodovod, kanalizacija, elektrika, plin, ceste, toplota) × distance_m + nearby_100m + 4 × nearby_500m variants
- **ML: Training speed**: 54 min total (was 170 min with v1 CatBoost params, ~3h with HistGBR+GPU false positive); global model depth 7 (was 8), 2000 iterations (was 3000), rsm=0.8 feature subsampling
- **ML: Results**: 8/9 types beat previous HistGBR — turisticni +9.3%, parcela +2.2%, industrijski +1.9%, garaza +1.0%, stanovanje +0.8%, poslovni_prostor +0.7%, gostinstvo +0.5%, hisa +0.3%; only kmetijsko -1.7%
- **Infra: CPU-only**: Hardcoded CPU mode — removed GPU detection that gave false positives on laptops without dedicated GPUs
- **Version**: 0.13.0 → 0.14.0

### v0.12.0

- **TypeScript**: Migrated stores, composables, and utilities to TypeScript; added `tsconfig.json`, `env.d.ts`, domain types in `src/types/api.ts`; build now runs `vue-tsc --noEmit` before `vite build`
- **VueUse**: Replaced manual localStorage/scroll/debounce patterns with `useLocalStorage`, `useWindowScroll`, `useDark`, `useDebounceFn`; token storage extracted to `stores/tokens.ts` to break circular deps
- **Vitest**: 46 frontend unit tests across stores, composables, utils, and components; coverage via `@vitest/coverage-v8`
- **Playwright E2E**: 8 end-to-end tests (auth flow, protected route redirects, page title, boot loader, console error checks); Playwright config with webServer auto-start
- **Auto-imports**: PrimeVue component resolver + Vue/Router/Pinia/VueUse API auto-imports via `unplugin-vue-components` and `unplugin-auto-import`
- **DB optimization**: Alembic migration adding indexes on `dataset_files.uploaded_by`, `model_runs.trained_by`, `training_jobs.created_at`; partial index for active jobs; FK constraints with `ondelete="SET NULL"`; N+1 COUNT+SELECT eliminated in 5 paginated endpoints via `func.count().over()` window functions; connection pool tuning (`pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`)
- **API security**: Security headers middleware (CSP, X-Frame-Options, HSTS, Permissions-Policy); JWT decode hardening with `require: ["exp", "sub"]`; rate limiting on login (5/min), upload (5/min), training (3/hour); CORS wildcard guard in production; `SecretStr` for password fields (never logged/serialized)
- **Performance**: Bundle splitting via `manualChunks` (vendor, primevue, vueuse); Lighthouse CI config with budgets (performance ≥ 0.85, accessibility ≥ 0.9); k6 load test script; Cache-Control headers on regions (1hr public), model info (60s private), stats (5min private)
- **Accessibility**: Skip navigation link; `aria-label` on all icon-only buttons; `aria-live="polite"` route title announcements for screen readers; `.sr-only` utility class; translation keys for `a11y.*`
- **CI/CD**: Enhanced GitHub Actions with Codecov coverage, Trivy security scan, Playwright E2E job; Dependabot for pip/npm/Docker/Actions; Prometheus metrics via `prometheus-fastapi-instrumentator`
- **Local dev**: `docker-compose.dev.yml` for backend-only Docker (no frontend container); Vite proxy env-configurable via `VITE_API_URL`
- **Bug fixes**: Fixed hard `window.location.href` redirect → `router.push`; fixed boot loading overlay with proper spinner; Prometheus import made fault-tolerant (graceful fallback when package not installed)
- **API contract tests**: TypeScript-based contract tests validating all 7 domain types match expected API response shapes
- **Version**: 0.11.0 → 0.12.0

### v0.11.0

- **Data truth**: Dashboard year coverage now comes from explicit earliest/latest metadata, viewer municipality metrics use canonical known municipalities only, and unresolved values like `Unknown` are moved out of consumer rankings into an admin quality summary
- **Reference seeding**: `region_lookup` is now seeded from a canonical municipality/region reference when empty, `/api/regions/municipalities` prefers that canonical source, and fallback data is demoted to an emergency backend safety net
- **Map UX**: The map now defaults to the latest complete year, keeps a persistent clickable low/mid/high price legend, supports municipality filtering, renders all filtered transactions without a silent default cap, and opens a large centered modal with richer property or municipality context
- **Prediction & analysis UX**: GPS latitude/longitude are moved behind an advanced location section, guided analysis now matches the model-backed listing profile more closely, and portal comparison uses direct `nepremicnine.net` location/type URLs instead of dead Google site-search links
- **Performance & UI system**: Dashboard/map analytics now use in-process prepared-data caching, shared PrimeVue styling was tightened across buttons, tables, dialogs, and controls, and the admin Data page now includes a searchable quality-focused workbench
- **Version**: 0.10.0 → 0.11.0

### v0.10.0

- **Training reliability**: Model training now publishes structured stage updates, current-model progress, elapsed time, ETA, and richer job/run history so admins can follow real work instead of a fake 0→100 jump
- **Map redesign**: The market map now defaults to transactions, exposes a clickable low/mid/high price-band legend, and opens a right-side drawer with property details, municipality drill-down, prediction prefill, and portal comparison actions
- **UI system**: Prediction and preparation flows now use PrimeVue controls more consistently, the shared theme tokens are tightened for dark mode, and checkbox/toggle alignment is cleaned up for a more professional feel
- **Canonical formatting**: Municipality and region labels keep Slovenian šumniki and proper capitalization across dashboard, map, autocomplete, and regional summaries
- **Release hygiene**: README, MASTER, package/config versions, `.env.example`, and the local `.env` APP_VERSION are all synced to the new release
- **Version**: 0.9.0 → 0.10.0

### v0.9.0

- **Viewer/admin split**: Viewers now stay in a market-first app with dashboard, prediction, map, analysis, and municipality pages, while admins get a separate `/admin` workbench for data, preparation, training, diagnostics, and users
- **UX reset**: Rebuilt the shell into a collapsible, scrollable navigation rail and refreshed dashboard/analysis flows around valuation and market comparison instead of training-first copy
- **Map/data reset**: Added `GET /api/stats/map-overview`, improved `map-transactions` empty-state reasons, and switched the map to work from prepared ETN data instead of depending on trained-model municipality artifacts
- **Canonical municipality handling**: ETN preparation now preserves display names with šumniki while also creating normalized matching fields/slugs for routing and model features
- **Frontend system**: Standardized the newer viewer/admin surfaces on PrimeVue with a custom theme preset and cleaned up missing locale keys such as `diag.allTypes`
- **Version**: 0.8.16 → 0.9.0

### v0.8.16

- **Diagnostics UX**: Rebuilt diagnostics around a property-type focus workflow with clearer summary cards, highlighted feature importance, and more scannable per-type review states
- **Locale formatting**: Added shared formatting helpers for numbers, currency, percentages, and dates so analytical pages respect the active SI/EN locale instead of leaking hardcoded Slovenian formatting
- **Analytical consistency**: Applied translated property-type labels and locale-aware output across Dashboard, Model, Map, Prediction, Municipality, Data, Prepare, Analysis, and Admin views
- **Verification**: Backend Ruff + targeted unit tests and frontend Prettier/ESLint/build all pass after the Phase 20 UI sweep
- **Version**: 0.8.15 → 0.8.16

### v0.8.15

- **Dashboard parity**: Restored a v1-style property-type market lens so the analytical dashboard can pivot between the whole ETN market and a selected property segment
- **Backend filtering**: Added property-type-aware filtering and cache keys for dashboard-facing stats endpoints (`market-home`, `regions`, and `trend`)
- **Frontend UX**: Added persistent property-type chips, translated property-type labels, and type-aware rendering for dashboard mix and recent-sales panels
- **Testing**: Added direct unit coverage for filtered stats routes without relying on the flaky HTTP-client test harness
- **Version**: 0.8.14 → 0.8.15

### v0.8.14

- **Cache coherency**: Training workers now invalidate Redis-backed model/stats caches as soon as a job completes instead of waiting for a later `/api/train/status/{job_id}` poll
- **Data freshness**: Preparing `train.csv` or importing RPE/RN region mappings now clears cached analytical responses so the dashboard reflects the newest source data immediately
- **Testing**: Added unit coverage for shared cache invalidation, worker cache clearing, and data/region mutation invalidation hooks
- **Planning**: Extended the agency-driven tracker with Phase 18–20 execution milestones for the remaining parity and UX work
- **Version**: 0.8.13 → 0.8.14

### v0.8.13

- **Training UX**: Added active-job recovery so the Model view can resume queued/running training jobs after refresh, and stale jobs are now marked failed instead of blocking new training forever
- **Data prep**: Dataset loading now walks every pagination page, bulk ETN preparation returns per-year row counts, and deduplication keys off stable source row IDs to avoid dropping legitimate transactions
- **Production UI**: Added real `favicon.ico`/PNG assets and updated nginx/icon links so browser tab icons render reliably in production
- **Analytical portal**: Added `GET /api/stats/market-home`, `GET /api/stats/municipality/{slug}`, and `GET /api/stats/comparables` for dashboard, municipality spotlight, and AVM comparable sales workflows
- **Frontend UX**: Rebuilt Dashboard, Prediction, and Map into a denser analytical portal and added a new authenticated municipality drill-down route at `/obcine/:slug`
- **Version**: 0.8.12 → 0.8.13

### v0.8.12
- **UX**: Rebuilt the authenticated shell with a real top header, better navigation context, cleaner landing/auth screen, and a stronger dashboard first impression
- **Workflow**: Prepared training dataset is now visible through the API and surfaced directly in the Model view as the recommended source
- **Profile**: Added editable profile settings (`PATCH /api/auth/me`) with optional avatar URLs
- **Production**: Raised nginx upload ceiling to 1024 MB, added favicon fallbacks for `/favicon.ico`, and always expose the app version from `/api/health`
- **i18n**: Mapped common backend error messages into SI/EN translations instead of leaking raw strings
- **Backend**: Training jobs and model runs now persist richer metadata after completion
- **Version**: 0.8.11 → 0.8.12

### v0.8.11
- **Fix**: Fix CI pipeline — backend ruff lint/format + frontend prettier format violations
- **Fix**: Fix production version stuck on v0.1.1 — stale `APP_VERSION` in VPS `.env`
- **Version**: 0.8.10 → 0.8.11

### v0.8.10
- **Docs**: Comprehensive documentation update — README, MASTER.md, PHASE_8_14_PLAN.md, DEPLOYMENT.md all updated to v0.8.10
- **Docs**: All Phase 8–14 verification checkboxes completed in plan doc
- **Docs**: Test count updated to 126 (from 111)
- **Version**: 0.8.9 → 0.8.10

### v0.8.9
- **Test**: 15 new tests added (111 → 126 total)
- **Test**: Phase 8 coverage — CC-SI prefix map validation, group property type classification
- **Test**: Phase 9 coverage — enriched score listing response fields, enhanced diagnostics fields
- **Test**: Phase 11 coverage — path traversal blocking, health endpoint redaction, generic error messages
- **Test**: Security tests — upload extension validation, bulk request limits, account enumeration prevention
- **Test**: New test files: test_data_processing.py, test_security.py
- **Version**: 0.8.8 → 0.8.9

### v0.8.8
- **A11y**: ARIA labels on all icon-only buttons (AdminView, DataView)
- **A11y**: Municipality autocomplete — role="combobox", aria-expanded, keyboard navigation (arrow keys + enter)
- **A11y**: Progress bar — role="progressbar" with aria-valuenow/min/max
- **A11y**: Tab pattern — role="tablist"/"tab"/"tabpanel" with aria-selected (PrepareView)
- **A11y**: Form accessibility — id/for on inputs/labels, novalidate, aria-describedby (LoginView)
- **A11y**: Global :focus-visible outline styles for buttons, inputs, selects, links
- **UX**: Page titles set via router meta + afterEach navigation guard
- **Version**: 0.8.7 → 0.8.8

### v0.8.7
- **Security**: Content-Security-Policy header added to FastAPI middleware and nginx (default-src 'self', script/style/img/font/connect restrictions, frame-ancestors 'none')
- **Security**: Permissions-Policy header added (geolocation, microphone, camera, payment disabled)
- **Security**: HSTS upgraded with `preload` directive
- **Security**: Nginx X-Frame-Options aligned to DENY, X-XSS-Protection set to 0 (modern standard)
- **Security**: Nginx body size reduced from 1G to 500M
- **Security**: Docs/OpenAPI proxy routes blocked in nginx (defense in depth — backend also disables in prod)
- **Security**: Symlink check added to file path validation (data.py, train.py)
- **Security**: Bulk request size limits added (EtnBulkRequest max 50 pairs, BulkDeleteRequest max 500 IDs)
- **Security**: Account enumeration fix — registration no longer confirms email existence
- **Security**: Admin role update error no longer leaks valid role enum values
- **Security**: Health endpoint redacts version/environment in production
- **Security**: JWT secret length validation (min 32 chars) enforced in production
- **Version**: 0.8.6 → 0.8.7

### v0.8.6
- **Refactor**: DRY up Redis cache helpers — extracted shared `cache_get`/`cache_set` into `app/utils/cache.py`, removed duplicated code from stats.py and model.py
- **Fix**: Stale `_cache_set` reference in model info endpoint
- **Cleanup**: Removed unused `json` import from model.py
- **Version**: 0.8.5 → 0.8.6

### v0.8.5
- **Feat**: Enriched score listings response — includes original listing fields (size_m2, rooms, municipality, property_type, etc.)
- **Feat**: Enhanced stats overview — added min/max/std price, year_built stats, regions_count, data_years
- **Feat**: Region stats now include min_price and max_price per region
- **Feat**: Enhanced model diagnostics — train_rows, test_rows, used_features, model_type, combined_metrics, type_models_trained
- **Frontend**: AnalysisView table shows property type, municipality, and area columns
- **Frontend**: DiagnosticsView shows combined routing metrics section, model type, trained types, train/test row counts
- **i18n**: Added diag.combinedMetrics, combinedDesc, trainRows, testRows, modelType, trainedTypes keys
- **Version**: 0.8.4 → 0.8.5

### v0.8.4
- **Fix (CRIT)**: Data leakage — group medians (price_per_m2_region, price_per_m2_type) now computed from training set only, after train/test split
- **Fix (CRIT)**: Warm-start loop — preprocessor (incl. TargetEncoder) now fitted once; warm-start loop only re-fits the regressor on transformed data
- **Fix (CRIT)**: D96/TM → WGS84 coordinate conversion — map-transactions now validates D96/TM ranges and vectorizes conversion (was showing raw D96/TM values)
- **Feat**: Combined routing metrics — training results now include end-to-end metrics for the per-type + global fallback routing system
- **Feat**: Region lookup by municipality code (sifra) — ETN enrichment now tries RPE_OBCINE_SIFRA first (unambiguous), then name-based fallback
- **Perf**: Map transactions response building vectorized — replaced iterrows() with df.to_dict(orient="records")
- **Version**: 0.8.3 → 0.8.4

### v0.8.3
- **Fix**: 413 upload error — host nginx `client_max_body_size` increased from 100M to 1G in deployment docs
- **Fix**: Version display showing stale value — `.env` and `.env.example` `APP_VERSION` now kept in sync with config.py
- **Fix**: Select-all checkbox in PrepareView — replaced mutating computed with reactive `deselectedYears` Set
- **Fix**: Dataset store only fetching page 1 (max 50) — now fetches up to 200 datasets per page
- **Feat**: "Delete all" button on Data page — uses existing bulk delete API endpoint
- **Feat**: Favicon added (house icon SVG) for browser tab
- **Security**: Viewer role restricted to Dashboard, Prediction, and Map pages only (Data, Model, Diagnostics, Analysis, Prepare, Admin require admin role)
- **UX**: File upload input now accepts `.zip` in addition to `.csv`
- **UX**: Nav sidebar hides admin-only pages from viewers
- **Infra**: Nginx `proxy_request_buffering off` for streaming uploads
- **i18n**: Added `data.deleteAll`, `data.confirmDeleteAll` keys to both locales
- **Version**: 0.8.0 → 0.8.3

### v0.8.0
- **Docs**: Comprehensive documentation update — all phases, changelog
- **Version**: 0.7.0 → 0.8.0

### v0.7.0
- **Perf**: Model cache invalidated after training (no stale predictions)
- **Perf**: Redis caching added to GET /stats/trend
- **DB**: Index on dataset_files.uploaded_at (ORDER BY performance)
- **DB**: Index on training_jobs.status (WHERE status IN queries)
- **DB**: UniqueConstraint on region_lookup prevents duplicate imports
- **Frontend**: CSV export composable + buttons in Prediction/Analysis views
- **Frontend**: DiagnosticsView tables show empty state when no metrics available
- **i18n**: predict.exportHistory, analysis.export keys
- **Version**: 0.6.0 → 0.7.0

### v0.6.0
- **Testing**: 61 → 111 tests passing
- **Fix**: pg_advisory_xact_lock guarded by dialect check (fixed SQLite test suite)
- **Tests**: New auth token rotation tests (5)
- **Tests**: New analysis runs/validation tests (5)
- **Tests**: New admin stats/pagination tests (5)
- **Version**: 0.5.0 → 0.6.0

### v0.5.0
- **Security**: Old refresh token blacklisted on token rotation
- **Perf**: In-process model cache eliminates per-request joblib reads
- **Fix**: LoginRequest.password max_length=128 (prevents bcrypt DoS)
- **Fix**: preview_dataset limit bounded (ge=1, le=1000)
- **Fix**: ListingItem validation: asking_price≥0, size_m2≥1
- **Security**: stored_path removed from DatasetFileResponse
- **Fix**: Concurrent training job guard (HTTP 409)
- **Feat**: Paginated GET /admin/users
- **Feat**: GET /analysis/runs endpoint
- **Feat**: GET /admin/stats platform usage endpoint
- **Frontend**: stats.js error handling
- **Frontend**: ModelView.vue pollTimer cleared on unmount
- **Frontend**: DataView.vue error handling + loading states
- **Frontend**: AdminView.vue empty state for users table
- **Frontend**: PredictionView.vue lega options translated
- **i18n**: predict.lega.*, model.defaultDataset keys
- **Version**: 0.4.0 → 0.5.0

### v0.4.0
- **Security (CRIT)**: Refresh token now blacklisted on logout
- **Security (CRIT)**: /refresh endpoint checks token blacklist
- **Security**: Rate limit on /refresh (10/min), /predict (30/min), /analysis/score (10/min)
- **Security**: Swagger/ReDoc/OpenAPI disabled in production
- **Security**: HSTS header added for production
- **Security**: TOCTOU race condition fixed in first-user admin promotion
- **Security**: source_type validated as Literal enum
- **Security**: Uploaded filename sanitized before storage
- **Fix**: Missing db.commit() in delete_dataset endpoint
- **Fix**: Raw exception messages no longer leaked to API callers
- **Frontend**: logout() sends refresh_token to server for full revocation
- **Version**: 0.3.1 → 0.4.0

### v0.3.1
- **Bug fix**: Increase nginx `client_max_body_size` from 100M to 600M — fixes 413 Request Entity Too Large on file uploads
- **Bug fix**: PrepareView `TypeError: M.value is not iterable` — defensive guard on datasets iteration when no files uploaded
- **Bug fix**: ModelView dropdown showing `(vrstic)` with no datasets — guard against null/empty dataset entries + null-safe row_count
- **Robustness**: Data store `fetchDatasets()` now guarantees `datasets` is always an array via `Array.isArray()` check
- **Version**: 0.3.0 → 0.3.1

### v0.3.0
- **Security**: Rate limiting on auth endpoints (slowapi, 5 req/min per IP)
- **Security**: Token blacklist for logout via Redis
- **Security**: Security response headers (X-Content-Type-Options, X-Frame-Options, Referrer-Policy)
- **Security**: Input range validation on prediction requests (Pydantic Field constraints)
- **Security**: Fixed silent exception swallowing — specific exceptions with logging throughout
- **ML**: Permutation importance (sklearn, n_repeats=3) replaces built-in feature_importances_
- **Backend**: Structured request logging middleware with correlation IDs (X-Request-ID)
- **Backend**: Global exception handler — structured JSON errors, no stack trace leaks
- **Backend**: Production-grade logging config (JSON format in prod, human-readable in dev)
- **Backend**: Redis caching for stats and model info endpoints (5-min TTL)
- **Backend**: Pagination for datasets, prediction history, training jobs, model runs
- **Backend**: Enhanced health check — DB, Redis, and model status
- **Backend**: GZip compression middleware
- **Backend**: Database indexes on prediction_logs and model_runs
- **Testing**: 14 → 96 tests covering all endpoint groups (auth, data, predict, train, model, stats, admin, analysis, regions)
- **Frontend**: Dark mode with system preference detection and localStorage persistence
- **Frontend**: Mobile responsive layout (hamburger menu, collapsible sidebar)
- **Frontend**: WCAG AA contrast fix for sidebar text
- **Frontend**: Loading spinners and empty state components
- **Frontend**: Toast notification system for API errors
- **Frontend**: Inline form validation (PredictionView, LoginView)
- **Frontend**: ARIA labels and keyboard navigation improvements
- **Frontend**: Axios request timeout (30s)
- **i18n**: Added missing locale keys for UI elements, validation, empty states
- **Version**: 0.2.5 → 0.3.0

### v0.2.5
- Rewrite ETN pair detection: use reactive `computed` (like v1) instead of fragile `watch` + imperative function
- Search both `original_name` AND `stored_path` for file role detection (posli/delistavb/zemljisca)
- Restrict year regex to `/(20\d{2})/` to avoid false 4-digit matches
- Pick latest upload per role per year (highest ID) when duplicates exist
- Add zemljisca file support to bulk preparation (optional, passed to API when detected)
- Version: 0.2.4 → 0.2.5

### v0.2.4
- Fix PrepareView i18n: added missing locale keys (`autoEtn`, `singleEtn`, `manualMapping`, `autoEtnDesc`, `singleEtnDesc`, `columnMapping`, `prepareButton`, `outputRows`, `outputColumns`, `year`, `noPairsDetected`, `noPairs`, `invalidJson`) to both sl.json and en.json
- Fix ETN pair detection: `detectEtnPairs()` now runs via `watch(datasets)` instead of `onMounted`, so it fires after async `fetchDatasets()` completes
- Version: 0.2.3 → 0.2.4

### v0.2.3
- Fix PrepareView.vue build error: multi-statement `@click` handler incompatible with Vue 3.5.30 compiler (extracted to `switchToBulk()` method)
- Fix backend ruff lint: import sort order in train.py, line length formatting in data.py
- Fix frontend Prettier formatting in PrepareView.vue
- Version: 0.2.2 → 0.2.3

### v0.2.2
- **Security**: Path traversal fix — all file-path endpoints validate paths stay within the data directory
- **Security**: ZIP slip fix — ZIP extraction validates no member escapes the target directory
- **Security**: Upload validation — 500 MB size limit + `.csv`/`.zip` extension allowlist
- **Security**: Password minimum 8 characters on registration
- **Security**: CORS tightened to explicit method/header allowlists
- **Security**: Error messages no longer leak internal paths to clients
- **Performance**: Bulk delete endpoints use SQL `DELETE FROM` instead of per-row ORM delete
- **Bug fix**: Prediction history scoped to current user (was returning all users' history)
- **Bug fix**: Added missing `/priprava` route for PrepareView (was in sidebar but not in router)
- **Code quality**: Inline imports moved to top-level
- **Version**: 0.2.1 → 0.2.2

### v0.2.1
- Fix CI pipeline: ruff format (backend) + Prettier (frontend) formatting issues
- Version bump across all config files

### v0.2.0
- **Backend**: Add model training history endpoints (GET/DELETE /model/runs), map transactions endpoint with region/year/municipality filters, manual column mapping endpoint (POST /data/prepare-train)
- **Frontend**: New PrepareView (3-tab data preparation), PredictionView expanded with 9 fields + municipality autocomplete, MapView transaction-level view with price/m² gradient + region/year filters, DashboardView with type filter + feature importance & per-type R² charts
- **Locales**: 60+ new i18n keys in both Slovenian and English
- **Version**: 0.1.2 → 0.2.0

## Architecture

```
                  ┌──────────────────┐
                  │   User Browser   │
                  └────────┬─────────┘
                           │
                  ┌────────▼─────────┐
                  │   Nginx (:80)    │  Static assets + SPA
                  │   Vue 3 SPA      │  reverse-proxy /api/
                  └────────┬─────────┘
                           │
                  ┌────────▼─────────┐
                  │  FastAPI (:8000)  │  REST API, auth, ML
                  │  Python 3.13     │  predict/train/stats
                  └──┬───────────┬───┘
                     │           │
          ┌──────────▼──┐   ┌───▼──────────┐
          │ PostgreSQL  │   │   Redis 7    │
          │ 17-alpine   │   │   Task queue │
          │ 7 tables    │   └───┬──────────┘
          └─────────────┘       │
                           ┌────▼──────────┐
                           │  ARQ Worker   │
                           │  Model train  │
                           └───────────────┘
```

## Tech Stack Details

| Layer | Technology | Version |
|-------|-----------|---------|
| Runtime | Python | 3.13 |
| Framework | FastAPI | 0.115+ |
| ORM | SQLAlchemy (async) | 2.0+ |
| Migrations | Alembic | 1.14+ |
| DB Driver | asyncpg | 0.30+ |
| Auth | python-jose (JWT, SecretStr) + bcrypt | — |
| Task Queue | ARQ | 0.26+ |
| ML | CatBoost (CatBoostRegressor) | 1.2+ |
| Rate Limiting | slowapi | 0.1.9+ |
| Monitoring | prometheus-fastapi-instrumentator | 7.0+ |
| Data | pandas + numpy | — |
| Frontend | Vue 3 (Composition API) + TypeScript | 3.5+ |
| Reactivity | VueUse | 14.0+ |
| State | Pinia | 3.0+ |
| Build | Vite | 8.x |
| Unit Tests | Vitest + @vue/test-utils | 4.1+ |
| E2E Tests | Playwright | 1.52+ |
| Charts | Chart.js + vue-chartjs | — |
| Maps | Leaflet | 1.9.4 |
| i18n | vue-i18n | 11.x |
| Lint (BE) | ruff | 0.8+ |
| Lint (FE) | ESLint (flat config) | 10.x |
| Package Mgr | pnpm | 9.15.4 |
| CI/CD | GitHub Actions + Dependabot | — |
| Security Scan | Trivy | — |
| Registry | GHCR | — |
| Containers | Docker Compose | v2 |
