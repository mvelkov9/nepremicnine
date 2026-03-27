# Nepremičnine v0.13.0

> Slovenian real estate valuation platform for buyers, sellers, investors, and companies — powered by machine learning on official ETN transaction data.

## What It Does

- **Guide viewers** through a market-first product with `Nadzorna plošča`, `Napoved`, `Zemljevid`, `Analiza`, and municipality detail pages
- **Keep admins separate** in a dedicated workbench for uploads, ETN preparation, model training, diagnostics, and user management
- **Track training live** with stage-aware progress, current model progress, elapsed time, ETA, job history, and completed model run history
- **Predict** residential property prices using per-type gradient boosting models trained on Slovenian ETN transaction data
- **Visualize** municipality leaders, recent sales, regional statistics, and transaction dots on a market map with a persistent clickable low/mid/high legend, municipality filters, and a large centered detail modal
- **Compare** model estimates with ranked comparable ETN transactions, municipality context, and external listing portals
- **Analyze** listings against trained models to identify over-, under-, or market-aligned pricing
- **Export** prediction history and analysis results to CSV
- **Preserve canonical names** for municipalities and regions, including Slovenian šumniki, while still supporting normalized matching/slugs
- **Keep consumer metrics clean** by excluding unresolved municipality labels such as `Unknown` from viewer-facing rankings while surfacing them in an admin data quality panel
- **Manage** datasets, model training, and users through a full admin interface
- **Refresh** model/statistical caches immediately after training completion, train.csv preparation, and region imports
- **Cache analytics in-process** so dashboard and map routes stop rereading and renormalizing the prepared CSV on every request
- **Personalize** user profiles with editable display names and optional avatars
- **Monitor** platform usage with an admin stats dashboard
- **Secure** with rate limiting, token blacklist, security headers, and input validation
- **Accessible** with dark mode, mobile responsive layout, WCAG AA contrast, and keyboard navigation

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI + Python 3.13 + uvicorn |
| Database | PostgreSQL 17 + SQLAlchemy 2.x (async) + Alembic |
| Cache | Redis 7 (caching + task queue + token blacklist) |
| Task Queue | ARQ + Redis 7 |
| ML | CatBoostRegressor (per property type + global, native categorical handling) |
| Security | slowapi rate limiting, security headers, SecretStr passwords, input validation |
| Frontend | Vue 3 (Composition API) + TypeScript + Pinia + VueUse + Vite 8 + PrimeVue 4 + Tailwind CSS 4 |
| Testing | Vitest (unit) + Playwright (E2E) + pytest (backend) |
| Charts | Chart.js + vue-chartjs |
| Maps | Leaflet 1.9 |
| Auth | JWT (access + refresh) with bcrypt |
| i18n | vue-i18n (Slovenian + English) |
| Monitoring | Prometheus metrics (`/metrics`), structured JSON logging |
| Lint | ruff (backend) + ESLint (frontend) |
| CI/CD | GitHub Actions → GHCR → VPS (SSH deploy), Trivy scan, Dependabot |
| Deploy | Docker Compose (dev + prod profiles) |

## Quick Start

### Option A — Fast Local Dev (recommended)

Run infra in Docker, frontend directly with `pnpm dev` for instant HMR:

```bash
# Clone and configure
git clone https://github.com/mvelkov9/nepremicnine.git
cd nepremicnine
cp .env.local.example .env          # uses localhost DB/Redis URLs
# Edit .env — set a real JWT_SECRET_KEY

# Start postgres, redis, backend, worker in Docker
docker compose -f docker-compose.dev.yml up -d --build

# Run frontend locally (instant hot-reload, no Docker rebuild)
cd frontend
pnpm install
pnpm dev

# Access the application
# Frontend:  http://localhost:5173
# Backend:   http://localhost:8000
# API docs:  http://localhost:8000/docs
```

### Option B — Full Docker

```bash
cp .env.example .env
# Edit .env — set JWT_SECRET_KEY to a real secret

docker compose up --build

# Frontend:  http://localhost:5173
# Backend:   http://localhost:8000
```

Development startup applies pending Alembic migrations automatically before the backend begins serving requests.

The first registered user is automatically assigned the **admin** role.

### Typical Workflow

1. Register an account (first user → admin)
2. As an admin, upload ETN CSV files from [GURS/ETN](https://www.e-prostor.gov.si/) via the Admin Data page
3. As an admin, prepare `raw/train.csv` from the Admin Prepare page
4. As an admin, trigger model training from the Admin Model page using the prepared dataset
5. Watch structured live progress during training, then review job history and completed model runs from the same admin page
6. As a viewer or admin, predict property prices from the Prediction page
7. Explore the dashboard, municipality detail pages, and map explorer
8. Analyze listings and compare them with direct `nepremicnine.net` location/type links

## Production Deployment

```bash
# On your server
git clone https://github.com/mvelkov9/nepremicnine.git
cd nepremicnine
cp .env.example .env

# Configure production values in .env:
#   POSTGRES_PASSWORD=<strong random password>
#   JWT_SECRET_KEY=<python3 -c "import secrets; print(secrets.token_urlsafe(64))">
#   APP_ENV=production
#   CORS_ORIGINS=https://yourdomain.com

# Launch with production overrides
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# Run database migrations
docker compose exec backend alembic upgrade head
```

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for detailed deployment instructions including multi-app VPS setups.

### CI/CD

On every push to `main`:

1. **backend-lint** → **backend-test** (pytest + coverage → Codecov)
2. **frontend-lint** → **frontend-test** (Vitest + coverage → Codecov) → **frontend-build**
3. **security-scan** (Trivy vulnerability scan for CRITICAL/HIGH)
4. **e2e-test** (Playwright, on PRs only)
5. **docker** (build + push images to GHCR)
6. **deploy** (SSH deploy to VPS)

On git tag (`v*`): all of the above.

Dependabot automatically opens PRs for outdated dependencies (pip weekly, npm weekly, Docker monthly, Actions monthly).

Production deployment is handled through git-based CI/CD; normal releases no longer require manual SSH update steps on the VPS.

Required GitHub Actions secrets:

| Secret | Description |
|--------|-------------|
| `VPS_HOST` | Server IP or hostname |
| `VPS_USER` | SSH username |
| `VPS_SSH_KEY` | Private SSH key |
| `VPS_APP_DIR` | Deployment directory on VPS |

## Project Structure

```
nepremicnine/
├── .github/
│   ├── workflows/ci.yml        # CI/CD (lint, test, build, security scan, E2E, deploy)
│   └── dependabot.yml          # Automated dependency updates
├── docker-compose.yml          # Full development stack (5 services)
├── docker-compose.dev.yml      # Backend-only stack (no frontend container)
├── docker-compose.prod.yml     # Production overrides
├── .env.example                # Environment template
│
├── backend/
│   ├── Dockerfile              # Multi-stage: builder → slim runtime
│   ├── entrypoint.sh           # Alembic migrations → app startup
│   ├── pyproject.toml          # Python deps + ruff + pytest + coverage config
│   ├── alembic/                # Database migrations
│   ├── app/
│   │   ├── main.py             # FastAPI app factory + security headers + Prometheus
│   │   ├── config.py           # Pydantic settings + production guards
│   │   ├── database.py         # Async SQLAlchemy engine + pool tuning
│   │   ├── models/             # 7 ORM models (User, Dataset, ModelRun, ...)
│   │   ├── schemas/            # Pydantic request/response schemas (SecretStr)
│   │   ├── api/                # Route modules (auth, data, stats, predict, ...)
│   │   ├── dependencies/       # Auth dependencies (JWT verification + hardening)
│   │   ├── services/           # Business logic (data processing, ML, regions)
│   │   └── tasks/              # ARQ async workers (model training)
│   ├── models/                 # Trained model artifacts (*.joblib)
│   └── tests/
│       ├── test_*.py           # pytest suites for API, ML, security, and stats
│       └── load/k6_smoke.js    # k6 load test script
│
└── frontend/
    ├── Dockerfile              # Multi-stage: node build → nginx
    ├── nginx.conf              # Reverse proxy + SPA + security headers
    ├── tsconfig.json            # TypeScript configuration
    ├── playwright.config.ts     # Playwright E2E test config
    ├── .lighthouserc.json       # Lighthouse CI performance budgets
    ├── eslint.config.js         # ESLint flat config
    ├── src/
    │   ├── views/              # Viewer pages + admin workbench
    │   ├── components/         # App shell, shared UI, loading spinners
    │   │   └── layout/         # AppSidebar, ProfileDialog sub-components
    │   ├── constants/          # Navigation and shared labels
    │   ├── stores/             # Pinia (auth, data, model, stats, ui, tokens)
    │   ├── composables/        # useApi, useDarkMode, useExport, useToast
    │   ├── types/              # TypeScript domain types (api.ts) + auto-generated
    │   ├── theme/              # PrimeVue custom theme preset
    │   ├── locales/            # i18n (sl.json, en.json)
    │   ├── router/             # Vue Router with auth guards + route announcements
    │   ├── styles/             # Global CSS (skip-link, sr-only, transitions)
    │   └── tests/
    │       ├── e2e/            # Playwright E2E tests (auth, navigation)
    │       ├── api/            # API contract tests
    │       ├── stores/         # Pinia store unit tests
    │       ├── composables/    # Composable unit tests
    │       ├── components/     # Component unit tests
    │       └── utils/          # Utility function unit tests
    └── index.html
```

## API Reference

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/health` | — | Health check |
| **Auth** | | | |
| POST | `/api/auth/register` | — | Register (first user → admin) |
| POST | `/api/auth/login` | — | Login (returns JWT pair) |
| POST | `/api/auth/refresh` | token | Refresh access token |
| GET | `/api/auth/me` | token | Current user profile |
| PATCH | `/api/auth/me` | token | Update name/avatar profile fields |
| **Data** | | | |
| POST | `/api/data/upload` | admin | Upload ETN CSV files |
| GET | `/api/data/datasets` | token | List uploaded datasets |
| GET | `/api/data/training-dataset` | token | Prepared `train.csv` metadata |
| GET | `/api/data/quality-summary` | admin | Data quality summary for unresolved municipalities, alias collisions, and reference coverage |
| DELETE | `/api/data/datasets/{id}` | admin | Delete a dataset |
| POST | `/api/data/prepare-etn-kpp` | admin | Prepare single ETN pair |
| POST | `/api/data/prepare-etn-kpp-bulk` | admin | Prepare bulk ETN pairs |
| POST | `/api/data/prepare-train` | admin | Manual column mapping |
| POST | `/api/data/datasets/delete-bulk` | admin | Bulk delete datasets |
| POST | `/api/data/regions/import-rpe-rn` | admin | Import RPE/RN region data |
| GET | `/api/data/preview/{id}` | token | Preview dataset rows |
| GET | `/api/data/inspect/{id}` | token | Inspect dataset columns & stats |
| **Stats** | | | |
| GET | `/api/stats/overview` | token | Dataset statistics summary |
| GET | `/api/stats/regions` | token | Per-region statistics |
| GET | `/api/stats/price-distribution` | token | Price distribution data |
| GET | `/api/stats/trend` | token | Price trend over time |
| GET | `/api/stats/market-home` | token | Analytical dashboard KPIs, canonical municipality coverage, earliest/latest year metadata, municipality leaders, latest sales |
| GET | `/api/stats/municipality/{slug}` | token | Municipality spotlight with trend, type mix, recent transactions |
| GET | `/api/stats/comparables` | token | Ranked comparable transactions for valuation context |
| GET | `/api/stats/map-overview` | token | Municipality centroids, activity counts, and backend-generated price-band legend metadata |
| GET | `/api/stats/map-transactions` | token | Individual transactions with map-ready coordinates, backend price bands, centered-detail-modal fields, municipality filter support, and `meta.reason` empty-state hints |
| GET | `/api/stats/municipalities-by-region` | token | Municipalities in a region (mapping or filtered list) |
| **Regions** | | | |
| GET | `/api/regions/municipalities` | token | Canonical municipality list sourced from `region_lookup` (fallback only if the reference table is empty) |
| GET | `/api/regions/regions` | token | Statistical regions |
| GET | `/api/regions/regions/stats` | token | Region-aggregated stats |
| **Training** | | | |
| POST | `/api/train/start` | admin | Start model training (async) |
| GET | `/api/train/status/{job_id}` | token | Training job status with stage, per-model progress, elapsed time, and ETA |
| GET | `/api/train/jobs` | token | List training jobs with structured live progress fields |
| DELETE | `/api/train/jobs/clear` | admin | Clear training job history |
| **Prediction** | | | |
| POST | `/api/predict` | token | Predict property price |
| GET | `/api/predict/history` | token | Prediction history (user-scoped) |
| DELETE | `/api/predict/history/clear` | admin | Clear all prediction history |
| **Model** | | | |
| GET | `/api/model/info` | token | Model metrics & info |
| GET | `/api/model/importance` | token | Feature importance |
| GET | `/api/model/runs` | admin | Completed model run history with metrics, duration, and source dataset |
| DELETE | `/api/model/runs/clear` | admin | Clear training history |
| GET | `/api/model/diagnostics` | token | Diagnostic metrics |
| **Analysis** | | | |
| POST | `/api/analysis/score` | token | Score listings vs model |
| GET | `/api/analysis/runs` | token | List analysis run history |
| **Admin** | | | |
| GET | `/api/admin/users` | admin | List all users (paginated) |
| PATCH | `/api/admin/users/{id}` | admin | Update user role/status |
| DELETE | `/api/admin/users/{id}` | admin | Delete user |
| GET | `/api/admin/stats` | admin | Platform usage statistics |

Full interactive API documentation available at `/docs` (Swagger UI).

## Development

```bash
# Install ruff (if not already installed)
pip install ruff

# Backend lint + format check
cd backend && ruff check . && ruff format --check .

# Backend auto-fix lint + format
cd backend && ruff check . --fix && ruff format .

# Backend tests (uses SQLite + fake Redis, no infra needed)
cd backend && pytest -v --cov=app

# Frontend lint + format check
cd frontend && pnpm lint && pnpm format:check

# Frontend unit tests (Vitest, 46 tests)
cd frontend && pnpm test

# Frontend unit tests with coverage
cd frontend && pnpm test:coverage

# TypeScript check
cd frontend && pnpm exec vue-tsc --noEmit

# Frontend build
cd frontend && pnpm build

# E2E tests (requires running frontend + backend)
cd frontend && pnpm test:e2e

# k6 load test (requires k6 installed + running backend)
k6 run backend/tests/load/k6_smoke.js
```

## Troubleshooting

### Docker build fails with `no space left on device`

If `docker compose up --build` fails with a path under `~/.docker/buildx/...` or `/var/lib/docker`, the machine is out of disk space rather than the app failing to compile.

Useful checks:

```bash
df -h
docker system df
```

Safe Docker cleanup options:

```bash
docker builder prune -af
docker image prune -af
docker container prune -f
docker system prune -af --volumes
```

Only run the last command if you are comfortable deleting stopped containers, unused images, build cache, and unused volumes.

For this repo specifically:

- The development `worker` now reuses the same backend image as the API service, which avoids creating a second full-size Python image on every rebuild.
- The biggest remaining source of growth is stale superseded images after repeated `docker compose up --build` runs, so `docker image prune -af` is the primary cleanup command when disk pressure returns.

## Documentation

- [Master Tracking](docs/MASTER.md) — project overview and phase progress
- [Phase 0: Foundation](docs/PHASE_0_FOUNDATION.md)
- [Phase 1: Backend Core](docs/PHASE_1_BACKEND.md)
- [Phase 2: Frontend Core](docs/PHASE_2_FRONTEND.md)
- [Phase 3: ML Pipeline](docs/PHASE_3_ML_PIPELINE.md)
- [Phase 4: Features](docs/PHASE_4_FEATURES.md)
- [Phase 5: Production](docs/PHASE_5_PRODUCTION.md)
- [Phase 6: v0.3.0 Hardening](docs/PHASE_6_V030.md)
- [Phase 7: v0.4.0–v0.8.0 Security & Features](docs/PHASE_7_V040_V080.md)
- [Phase 8–20: v0.8.4–v0.8.16 Upgrades](docs/PHASE_8_14_PLAN.md)
- [Phase 21: v0.10.0 Market UX & Training Reliability Reset](docs/MASTER.md#v0100)
- [Phase 22: v0.11.0 Data Quality, Map UX, and PrimeVue Modernization](docs/MASTER.md#v0110)
- [Phase 23: v0.12.0 Architecture Modernization](docs/PHASE_23_MODERNIZATION.md)
- [Phase 24: v0.13.0 Full Frontend Redesign](docs/PHASE_24_REDESIGN.md)
- [Deployment Guide](docs/DEPLOYMENT.md)

## License

MIT
