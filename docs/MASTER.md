# Nepremičnine v0.2 — Master Tracking

## Overview

Complete rebuild of the Slovenian real estate price prediction application — from diploma prototype to a production-grade, publicly deployed platform.

| Item | Value |
|------|-------|
| **Version** | 0.3.0 |
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

## Changelog

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
