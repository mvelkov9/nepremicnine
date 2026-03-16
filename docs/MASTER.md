# Nepremičnine v0.3 — Master Tracking

## Overview

Complete rebuild of the Slovenian real estate price prediction application — from diploma prototype to a production-grade, publicly deployed platform.

| Item | Value |
|------|-------|
| **Version** | 0.8.5 |
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
| [Phase 8–14](PHASE_8_14_PLAN.md) | v1→v2 gap fixes, feature parity, performance, security, UX, tests, docs | 🔄 In Progress | — |

## Changelog

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
