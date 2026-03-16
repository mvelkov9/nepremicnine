# Nepremičnine v0.8.16

> Slovenian real estate price analysis & prediction platform — powered by machine learning on official ETN transaction data.

## What It Does

- **Predict** residential property prices using per-type gradient boosting models trained on real Slovenian transaction data (GURS ETN)
- **Visualize** market trends, municipality leaders, recent sales, and regional statistics on an analytical dashboard and map explorer, including a property-type lens
- **Review** model quality with focused diagnostics, top-feature highlights, and locale-aware number/date formatting across analytical workflows
- **Compare** predictions against ranked comparable ETN transactions and municipality-level market context
- **Analyze** listings against trained models to identify over/under-priced properties
- **Export** prediction history and analysis results to CSV
- **Manage** datasets, model training, and users through a full admin interface
- **Refresh** model/statistical caches immediately after training completion, train.csv preparation, and region imports
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
| ML | scikit-learn HistGradientBoostingRegressor (per property type) |
| Security | slowapi rate limiting, security headers, input validation |
| Frontend | Vue 3 (Composition API) + Pinia + Vite 6 |
| Charts | Chart.js + vue-chartjs |
| Maps | Leaflet 1.9 |
| Auth | JWT (access + refresh) with bcrypt |
| i18n | vue-i18n (Slovenian + English) |
| Lint | ruff (backend) + ESLint (frontend) |
| CI/CD | GitHub Actions → GHCR → VPS (SSH deploy) |
| Deploy | Docker Compose (dev + prod profiles) |

## Quick Start

```bash
# Clone and configure
git clone https://github.com/mvelkov9/nepremicnine.git
cd nepremicnine
cp .env.example .env
# Edit .env — set JWT_SECRET_KEY to a real secret

# Start all services
docker compose up --build

# Access the application
# Frontend:  http://localhost:5173
# Backend:   http://localhost:8000
# API docs:  http://localhost:8000/docs
```

Development startup applies pending Alembic migrations automatically before the backend begins serving requests.

The first registered user is automatically assigned the **admin** role.

### Typical Workflow

1. Register an account (first user → admin)
2. Upload ETN CSV files from [GURS/ETN](https://www.e-prostor.gov.si/) via the Data page
3. Prepare `raw/train.csv` from the Prepare page
4. Trigger model training from the Model page using the prepared dataset
5. Predict property prices from the Prediction page
6. Explore the analytical dashboard, municipality detail pages, and map explorer
7. Analyze listings

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

On every push to `main`: lint → test → build → push Docker images to GHCR.

On git tag (`v*`): all of the above + SSH deploy to VPS.

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
├── .github/workflows/ci.yml    # CI/CD (lint, test, build, deploy)
├── docker-compose.yml          # Development stack (5 services)
├── docker-compose.prod.yml     # Production overrides
├── .env.example                # Environment template
│
├── backend/
│   ├── Dockerfile              # Multi-stage: builder → slim runtime
│   ├── pyproject.toml          # Python deps + ruff config
│   ├── alembic/                # Database migrations
│   ├── app/
│   │   ├── main.py             # FastAPI app factory
│   │   ├── config.py           # Pydantic settings
│   │   ├── database.py         # Async SQLAlchemy engine
│   │   ├── models/             # 7 ORM models (User, Dataset, ModelRun, ...)
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   ├── api/                # Route modules (auth, data, stats, predict, ...)
│   │   ├── dependencies/       # Auth dependencies (JWT verification)
│   │   ├── services/           # Business logic (data processing, ML, regions)
│   │   └── tasks/              # ARQ async workers (model training)
│   ├── models/                 # Trained model artifacts (*.joblib)
│   └── tests/                  # pytest suites for API, ML, security, and stats
│
└── frontend/
    ├── Dockerfile              # Multi-stage: node build → nginx
    ├── nginx.conf              # Reverse proxy + SPA + security headers
    ├── eslint.config.js        # ESLint flat config
    ├── src/
    │   ├── views/              # 11 page components incl. municipality detail
    │   ├── components/         # AppLayout (sidebar + nav)
    │   ├── stores/             # Pinia (auth, data, model, stats)
    │   ├── composables/        # useApi (axios + JWT refresh)
    │   ├── locales/            # i18n (sl.json, en.json)
    │   └── router/             # Vue Router with auth guards
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
| GET | `/api/stats/market-home` | token | Analytical dashboard KPIs, municipality leaders, latest sales |
| GET | `/api/stats/municipality/{slug}` | token | Municipality spotlight with trend, type mix, recent transactions |
| GET | `/api/stats/comparables` | token | Ranked comparable transactions for valuation context |
| GET | `/api/stats/map-transactions` | token | Individual transactions with location |
| GET | `/api/stats/municipalities-by-region` | token | Municipalities in a region (mapping or filtered list) |
| **Regions** | | | |
| GET | `/api/regions/municipalities` | token | Municipality list |
| GET | `/api/regions/regions` | token | Statistical regions |
| GET | `/api/regions/regions/stats` | token | Region-aggregated stats |
| **Training** | | | |
| POST | `/api/train/start` | admin | Start model training (async) |
| GET | `/api/train/status/{job_id}` | token | Training job status |
| GET | `/api/train/jobs` | token | List all training jobs |
| DELETE | `/api/train/jobs/clear` | admin | Clear training job history |
| **Prediction** | | | |
| POST | `/api/predict` | token | Predict property price |
| GET | `/api/predict/history` | token | Prediction history (user-scoped) |
| DELETE | `/api/predict/history/clear` | admin | Clear all prediction history |
| **Model** | | | |
| GET | `/api/model/info` | token | Model metrics & info |
| GET | `/api/model/importance` | token | Feature importance |
| GET | `/api/model/runs` | token | Model training history |
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
# Backend lint + format
docker compose exec backend ruff check .
docker compose exec backend ruff format .

# Backend tests
docker compose exec backend pytest -v

# Frontend lint
docker compose exec frontend npx eslint src/

# Frontend build check
docker compose exec frontend pnpm build
```

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
- [Deployment Guide](docs/DEPLOYMENT.md)

## License

MIT
