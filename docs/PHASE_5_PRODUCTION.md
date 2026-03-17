# Phase 5: Production

**Status:** ✅ Complete  
**Commit:** `153f140`

> Historical note: Phase 5 originally shipped with a Vite-built frontend served by nginx. The current `feat/nuxt-ui-redesign` branch now serves the frontend through Nuxt 3 + Nitro and uses a same-origin `/api/*` proxy instead of an internal nginx frontend layer.

## Checklist

- [x] Production Dockerfiles (multi-stage builds, non-root `appuser`)
- [x] Backend health check (httpx self-check on `/api/health`)
- [x] Production docker-compose overrides (`docker-compose.prod.yml`)
- [x] Frontend nginx reverse proxy (static + /api/ proxy + gzip + security headers)
- [x] GitHub Actions CI: ruff lint, ruff format, pytest, ESLint, pnpm build
- [x] GitHub Actions: Docker build & push to GHCR on main/tags
- [x] GitHub Actions: SSH deploy to VPS on `v*` tags
- [x] Alembic migrations run automatically on deploy
- [x] `.env.example` with all required configuration variables
- [x] README with architecture, quick start, production deploy, API reference

## CI/CD Pipeline

```
Push to main / PR:
  ┌─────────────┐    ┌──────────────┐
  │ backend-lint│───▶│ backend-test │
  │ ruff check  │    │ pytest 14    │
  │ ruff format │    │ tests        │
  └─────────────┘    └──────┬───────┘
                            │
  ┌──────────────┐   ┌──────▼───────┐     ┌──────────┐
  │ frontend-lint│──▶│frontend-build│────▶│  docker   │
  │ ESLint       │   │ pnpm build   │     │ GHCR push │
  └──────────────┘   └──────────────┘     └────┬─────┘
                                               │
Tag v*:                                   ┌────▼─────┐
                                          │  deploy  │
                                          │ SSH→VPS  │
                                          └──────────┘
```

## Docker Architecture

### Development (`docker compose up`)
- **postgres** (17-alpine) — port 5432, pgdata volume
- **redis** (7-alpine) — port 6379, AOF persistence
- **backend** — port 8000, source-mounted, `--reload`
- **worker** — ARQ worker, source-mounted
- **frontend** — port 3000, Nuxt dev server with HMR

### Production (`docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`)
- **postgres** — no exposed port
- **redis** — no exposed port
- **backend** — `127.0.0.1:8000`, non-root user, 2 workers
- **worker** — non-root user
- **frontend** — port 80, Nuxt/Nitro Node server exposed as `80:3000`

## Security

- Non-root container users (`appuser`)
- JWT secrets via environment variables
- CORS restricted to configured origins
- Nginx security headers (X-Frame-Options, X-Content-Type-Options, Referrer-Policy, X-XSS-Protection)
- Database passwords via environment variables (never committed)
- PostgreSQL/Redis not exposed in production
- SHA-256 file hash deduplication prevents duplicate uploads

## Required GitHub Actions Secrets

| Secret | Purpose |
|--------|---------|
| `VPS_HOST` | Server IP or hostname |
| `VPS_USER` | SSH username |
| `VPS_SSH_KEY` | Private SSH key for deployment |
| `VPS_APP_DIR` | Deployment directory on VPS |
