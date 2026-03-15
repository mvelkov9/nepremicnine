# Nepremicnine v0.1

> Slovenian real estate price analysis & prediction — production rebuild.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI + Python 3.13 + uvicorn |
| Database | PostgreSQL 17 + SQLAlchemy 2.x + Alembic |
| Task Queue | ARQ + Redis 7 |
| Frontend | Vue 3 (Composition API) + Pinia + Vite 6 |
| Auth | JWT (access + refresh tokens) |
| i18n | vue-i18n (SI + EN) |
| CI/CD | GitHub Actions |
| Deploy | Docker Compose on VPS |

## Quick Start (Development)

```bash
# Clone
git clone https://github.com/mvelkov9/nepremicnine.git
cd nepremicnine

# Copy environment file
cp .env.example .env

# Start all services
docker compose up --build

# Access
# Frontend:  http://localhost:5173
# Backend:   http://localhost:8000
# API docs:  http://localhost:8000/docs
```

## Project Structure

```
nepremicnine/
├── backend/          # FastAPI application
├── frontend/         # Vue 3 SPA
├── docs/             # Project documentation & tracking
├── .github/          # CI/CD workflows
└── docker-compose.yml
```

## Documentation

See [docs/MASTER.md](docs/MASTER.md) for the full rebuild plan and progress tracking.

## License

MIT
