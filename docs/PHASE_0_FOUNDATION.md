# Phase 0: Foundation

**Status:** ✅ Complete

## Checklist

- [x] Init repo at github.com/mvelkov9/nepremicnine
- [x] Create monorepo directory structure
- [x] Backend: FastAPI app factory + health endpoint
- [x] Backend: pydantic-settings config
- [x] Backend: async SQLAlchemy database setup
- [x] Backend: User model (admin/viewer roles)
- [x] Backend: Alembic migration setup
- [x] Backend: Dockerfile (multi-stage, python:3.13-slim)
- [x] Backend: pytest health test
- [x] Frontend: package.json with Vue 3.5, Pinia, vue-i18n, Vite 6
- [x] Frontend: Router with 9 routes + auth guards
- [x] Frontend: Pinia auth store with JWT
- [x] Frontend: useApi composable with interceptors
- [x] Frontend: i18n locales (sl + en)
- [x] Frontend: AppLayout component (sidebar + nav)
- [x] Frontend: main.css design system
- [x] Frontend: All view stubs (Login, Dashboard, Data, Model, Prediction, Map, Diagnostics, Analysis, Admin)
- [x] Frontend: Dockerfile (node:24 → nginx:alpine)
- [x] Frontend: nginx.conf with SPA + API proxy
- [x] docker-compose.yml (postgres + redis + backend + frontend)
- [x] .env.example with all variables
- [x] GitHub Actions CI (lint + test + build)
- [x] Tracking docs (MASTER.md + phase files)
- [x] Verify: docker compose up → all services healthy

## Key Files Created

| File | Purpose |
|------|---------|
| `backend/app/main.py` | FastAPI app factory with lifespan |
| `backend/app/config.py` | pydantic-settings |
| `backend/app/database.py` | Async SQLAlchemy engine |
| `backend/app/models/user.py` | User ORM model |
| `frontend/src/components/AppLayout.vue` | Sidebar layout |
| `frontend/src/stores/auth.js` | JWT auth store |
| `docker-compose.yml` | 4-service stack |
| `.github/workflows/ci.yml` | CI pipeline |
