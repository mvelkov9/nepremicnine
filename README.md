# Nepremičnine v0.1

> Slovenian real estate price analysis & prediction — production rebuild.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI + Python 3.13 + uvicorn |
| Database | PostgreSQL 17 + SQLAlchemy 2.x async + Alembic |
| Task Queue | ARQ + Redis 7 |
| Frontend | Vue 3 (Composition API) + Pinia + Vite 6 |
| Auth | JWT (access + refresh tokens) with bcrypt |
| i18n | vue-i18n (SI + EN) |
| CI/CD | GitHub Actions → GHCR → VPS |
| Deploy | Docker Compose (dev + prod profiles) |

## Quick Start (Development)

```bash
# Clone
git clone https://github.com/mvelkov9/nepremicnine.git
cd nepremicnine

# Environment
cp .env.example .env
# Edit .env — at minimum set a real JWT_SECRET_KEY

# Start all 5 services (postgres, redis, backend, worker, frontend)
docker compose up --build

# Access
# Frontend:  http://localhost:5173
# Backend:   http://localhost:8000
# API docs:  http://localhost:8000/docs
```

The first registered user is automatically assigned the **admin** role.

## Production Deployment

```bash
# On your VPS: clone, configure, and launch
git clone https://github.com/mvelkov9/nepremicnine.git
cd nepremicnine

cp .env.example .env
# Edit .env:
#   POSTGRES_PASSWORD=<strong random password>
#   JWT_SECRET_KEY=<python -c "import secrets; print(secrets.token_urlsafe(64))">
#   APP_ENV=production
#   CORS_ORIGINS=https://yourdomain.com

# Launch with production overrides (nginx frontend, non-root backend, no source mounts)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# Run database migrations
docker compose exec backend alembic upgrade head
```

### CI/CD (automated)

On every push to `main`: lint → test → build & push Docker images to GHCR.

On git tag (`v*`): all of the above, then SSH-deploy to VPS.

Required GitHub Actions secrets for deploy:
- `VPS_HOST` — server IP or hostname
- `VPS_USER` — SSH user
- `VPS_SSH_KEY` — private SSH key
- `VPS_APP_DIR` — deployment directory on VPS

## Project Structure

```
nepremicnine/
├── .github/workflows/ci.yml    # CI/CD pipeline
├── docker-compose.yml          # Development (hot reload, source mounts)
├── docker-compose.prod.yml     # Production overrides (nginx, non-root)
├── .env.example                # Environment variable template
│
├── backend/
│   ├── Dockerfile              # Multi-stage: builder → slim runtime
│   ├── pyproject.toml          # Python deps
│   ├── alembic/                # Database migrations
│   ├── app/
│   │   ├── main.py             # FastAPI app factory
│   │   ├── config.py           # Pydantic settings
│   │   ├── models/             # SQLAlchemy ORM (User, Dataset, etc.)
│   │   ├── api/                # Route modules (auth, data, stats, ...)
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   ├── services/           # Business logic (data processing, ML, regions)
│   │   └── tasks/              # ARQ async workers (model training)
│   └── tests/                  # pytest async tests
│
└── frontend/
    ├── Dockerfile              # Multi-stage: node build → nginx
    ├── nginx.conf              # Reverse proxy + SPA + security headers
    ├── src/
    │   ├── views/              # Page components (Dashboard, Map, Model, ...)
    │   ├── components/         # Shared UI components (AppLayout)
    │   ├── stores/             # Pinia stores (auth, model)
    │   ├── composables/        # useApi (axios + JWT refresh)
    │   ├── locales/            # i18n (sl.json, en.json)
    │   └── router/             # Vue Router with auth guards
    └── index.html
```

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/health` | — | Health check |
| POST | `/api/auth/register` | — | Register user |
| POST | `/api/auth/login` | — | Login (returns JWT) |
| POST | `/api/auth/refresh` | token | Refresh access token |
| GET | `/api/auth/me` | token | Current user profile |
| POST | `/api/data/upload` | admin | Upload CSV datasets |
| GET | `/api/data/datasets` | token | List datasets |
| DELETE | `/api/data/datasets/{id}` | admin | Delete dataset |
| GET | `/api/regions/municipalities` | token | Municipality list |
| GET | `/api/stats/overview` | token | Dataset statistics |
| GET | `/api/stats/regions` | token | Per-region stats |
| POST | `/api/train/start` | admin | Start model training |
| GET | `/api/train/status/{job_id}` | token | Training job status |
| POST | `/api/predict` | token | Predict price |
| GET | `/api/model/info` | token | Model metrics/info |
| GET | `/api/model/importance` | token | Feature importance |
| POST | `/api/analysis/score` | token | Score listings vs model |
| GET | `/api/admin/users` | admin | List all users |
| PATCH | `/api/admin/users/{id}` | admin | Update user role/status |
| DELETE | `/api/admin/users/{id}` | admin | Delete user |

Full interactive docs at `/docs` (Swagger UI).

## License

MIT
