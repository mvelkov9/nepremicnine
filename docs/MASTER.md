# Nepremičnine v0.1 — Master Tracking

## Overview
Complete rebuild of the Slovenian real estate price prediction app.

| Item | Value |
|------|-------|
| **Version** | 0.1 |
| **Repo** | github.com/mvelkov9/nepremicnine |
| **Backend** | FastAPI + Python 3.13 + PostgreSQL 17 + SQLAlchemy 2 async |
| **Frontend** | Vue 3 Composition API + Pinia + pnpm + Vite 6 |
| **Auth** | JWT (admin/viewer roles) |
| **i18n** | Slovenian (default) + English |
| **CI/CD** | GitHub Actions → Docker → VPS |

## Phase Progress

| Phase | Description | Status |
|-------|-------------|--------|
| [Phase 0](PHASE_0_FOUNDATION.md) | Foundation — skeleton, Docker, CI | ✅ Complete |
| [Phase 1](PHASE_1_BACKEND.md) | Backend Core — ORM, auth, CRUD | 🔲 Not started |
| [Phase 2](PHASE_2_FRONTEND.md) | Frontend Core — pages, charts, i18n | 🔲 Not started |
| [Phase 3](PHASE_3_ML_PIPELINE.md) | ML Pipeline — training, prediction | 🔲 Not started |
| [Phase 4](PHASE_4_FEATURES.md) | Features — map, diagnostics, admin | 🔲 Not started |
| [Phase 5](PHASE_5_PRODUCTION.md) | Production — deploy, SSL, monitoring | 🔲 Not started |

## Architecture

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Frontend │───▶│  Nginx   │───▶│ FastAPI  │───▶│ Postgres │
│ Vue 3    │    │  :80     │    │  :8000   │    │  :5432   │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
                                     │
                                     ▼
                                ┌──────────┐
                                │  Redis   │
                                │  :6379   │
                                └──────────┘
```
