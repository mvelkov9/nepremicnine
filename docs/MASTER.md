# Nepremičnine — Master Tracking

## Overview

Complete rebuild of the Slovenian real estate price prediction application — from diploma prototype to a production-grade, publicly deployed platform.

| Item | Value |
|------|-------|
| **Version** | 0.8.16 |
| **Repo** | [github.com/mvelkov9/nepremicnine](https://github.com/mvelkov9/nepremicnine) |
| **Backend** | FastAPI + Python 3.13 + PostgreSQL 17 + SQLAlchemy 2.x async |
| **Frontend** | Vue 3 Composition API + Pinia + pnpm 9, Vite 6 |
| **ML** | scikit-learn HistGradientBoostingRegressor (per-type) |
| **Auth** | JWT (access 15 min + refresh 7 days), admin/viewer roles |
| **i18n** | Slovenian (default) + English |
| **CI/CD** | GitHub Actions → GHCR → VPS (SSH) |
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
| [Phase 20](PHASE_8_14_PLAN.md#phase-20--diagnostics-focus--locale-formatting-v0816) | Diagnostics focus workflow and locale-aware formatting polish | ✅ Complete | — |

## Changelog

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
| Auth | python-jose (JWT) + bcrypt | — |
| Task Queue | ARQ | 0.26+ |
| ML | scikit-learn (HistGBR) | 1.6+ |
| Rate Limiting | slowapi | 0.1.9+ |
| Data | pandas + numpy | — |
| Frontend | Vue 3 (Composition API) | 3.5+ |
| State | Pinia | 2.3+ |
| Build | Vite | 6.x |
| Charts | Chart.js + vue-chartjs | — |
| Maps | Leaflet | 1.9.4 |
| i18n | vue-i18n | 11.x |
| Lint (BE) | ruff | 0.8+ |
| Lint (FE) | ESLint (flat config) | 9.x |
| Package Mgr | pnpm | 9.15.4 |
| CI/CD | GitHub Actions | — |
| Registry | GHCR | — |
| Containers | Docker Compose | v2 |
