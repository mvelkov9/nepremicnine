# Phase 23 — Architecture Modernization (v0.12.0)

> Full-stack modernization: TypeScript, VueUse, Vitest, Playwright E2E, database optimization, API security hardening, performance benchmarking, accessibility audit, CI/CD overhaul, and Prometheus monitoring.

| Item | Value |
|------|-------|
| **From Version** | 0.11.0 |
| **To Version** | 0.12.0 |
| **Scope** | 15 sub-phases covering frontend tooling, backend hardening, testing, CI/CD, performance, and accessibility |
| **Method** | Agency agent-driven analysis and implementation |

---

## Sub-Phases

| # | Area | Description | Status |
|---|------|-------------|--------|
| 1 | Bug fixes | Vite proxy Docker-only fix, hard redirect → router.push, boot loading spinner, missing aiosqlite dep | ✅ |
| 2 | Local dev | `docker-compose.dev.yml` (no frontend container), env-configurable proxy target | ✅ |
| 3 | VueUse | Replaced manual localStorage/scroll/debounce with VueUse composables | ✅ |
| 4 | Vitest | 46 frontend unit tests, coverage via `@vitest/coverage-v8`, happy-dom environment | ✅ |
| 5 | TypeScript | Gradual migration of stores, composables, utils; `tsconfig.json`; domain types `api.ts` | ✅ |
| 6 | Page transitions | `FullPageSpinner.vue`, route transition animations, `useUiStore` loading state | ✅ |
| 7 | Component arch | Auto-imports (PrimeVue resolver + Vue/Router/Pinia/VueUse), bundle splitting | ✅ |
| 8 | Backend | pytest asyncio_mode auto, coverage config, Cache-Control headers, entrypoint.sh | ✅ |
| 9 | DB optimization | Indexes, FK constraints, N+1 fixes (window functions), connection pool tuning | ✅ |
| 10 | API security | Security headers, JWT hardening, rate limiting, CORS guard, SecretStr passwords | ✅ |
| 11 | Performance | Lighthouse CI, manualChunks, k6 load test, Cache-Control strategy | ✅ |
| 12 | Accessibility | Skip link, ARIA labels, sr-only, route announcements, a11y translations | ✅ |
| 13 | API testing | TypeScript contract tests for 7 domain types | ✅ |
| 14 | CI/CD | Enhanced GitHub Actions, Dependabot, Prometheus metrics | ✅ |
| 15 | E2E testing | Playwright config, 8 E2E tests (auth + navigation), CI job with artifact upload | ✅ |

---

## Phase 1–2: Bug Fixes & Local Dev

### Bug fixes
- **Vite proxy**: Proxy target changed from hardcoded `http://backend:8000` to `env.VITE_API_URL || 'http://localhost:8000'`
- **Hard redirect**: Replaced `window.location.href = '/login'` with `router.push({ name: 'login' })`
- **Boot loading**: Replaced unstyled `<p>` with `<LoadingSpinner />` inside a full-page overlay
- **Missing dep**: Added `aiosqlite>=0.20.0` to backend dev dependencies

### Local dev setup
- Created `docker-compose.dev.yml` — same as main compose but **no frontend service** (postgres, redis, backend, worker only)
- Frontend runs locally via `pnpm dev` with Vite proxy to `localhost:8000`
- Backend uses `entrypoint.sh` that runs `alembic upgrade head` before starting uvicorn

```bash
# Fast local dev:
docker compose -f docker-compose.dev.yml up -d
cd frontend && pnpm dev

# Full Docker:
docker compose up --build
```

---

## Phase 3: VueUse Integration

### Replacements

| File | Before | After |
|------|--------|-------|
| `useDarkMode.ts` | Manual localStorage + system preference detection (~30 lines) | `useDark` + `useToggle` (~5 lines) |
| `AppLayout.vue` | `localStorage.getItem('sidebar_collapsed')` + scroll listeners | `useLocalStorage` + `useWindowScroll` |
| `stores/auth.ts` | `localStorage.setItem/removeItem` for tokens | `useLocalStorage` via `stores/tokens.ts` |
| `i18n.ts` | Manual localStorage for locale | `useLocalStorage('locale', 'sl')` |
| Search inputs | Manual setTimeout debounce | `useDebounceFn` |

### Token Architecture
Extracted `stores/tokens.ts` as module-level reactive refs to break the circular dependency: `auth.ts → useApi.js → tokens.ts` (no cycle).

---

## Phase 4–5: Vitest & TypeScript

### Vitest
- Environment: `happy-dom`
- Setup: `src/tests/setup.ts` (creates fresh Pinia per test)
- 46 tests across: `stores/`, `composables/`, `utils/`, `components/`
- Coverage: `@vitest/coverage-v8` with `v8` provider

### TypeScript
- `tsconfig.json` with `allowJs: true`, `strict: false` (gradual migration)
- Domain types in `src/types/api.ts`: `User`, `Dataset`, `TrainingJob`, `ModelRun`, `ModelInfo`, `PredictionPayload`, `PredictionResult`, `RegionLookup`, `HealthStatus`
- Build script: `vue-tsc --noEmit && vite build`

### Migrated files
- `stores/auth.ts`, `stores/ui.ts`, `stores/data.ts`, `stores/model.ts`, `stores/stats.ts`
- `composables/useDarkMode.ts`, `composables/useExport.ts`
- `utils/format.ts`, `utils/apiError.ts`, `utils/municipality.ts`, `utils/propertyType.ts`, `utils/externalSearch.ts`
- `stores/tokens.ts` (new)

---

## Phase 6–7: Page Transitions & Component Architecture

### Page transitions
- `FullPageSpinner.vue` — teleported to body, thin progress bar at top + centered spinner on initial boot
- Route transitions via `<Transition name="page-fade" mode="out-in">` in `App.vue`
- `useUiStore` tracks `routeTransitioning` state, set by router guards

### Auto-imports
- PrimeVue components auto-resolved via `@primevue/auto-import-resolver`
- Vue/Router/Pinia/VueUse APIs auto-imported via `unplugin-auto-import`
- Generated declaration files: `src/types/components.d.ts`, `src/types/auto-imports.d.ts`

### Bundle splitting
```js
manualChunks: {
  'vendor': ['vue', 'vue-router', 'pinia', 'vue-i18n'],
  'primevue': ['primevue'],
  'vueuse': ['@vueuse/core'],
}
```

---

## Phase 8: Backend Improvements

- `asyncio_mode = "auto"` in `pyproject.toml` — eliminates `@pytest.mark.asyncio` boilerplate
- Coverage config: `source = ["app"]`, `omit = ["app/tasks/*"]`, `fail_under = 70`
- Cache-Control headers on stats endpoints (5-min private)
- `entrypoint.sh` separates Alembic migrations from uvicorn startup

---

## Phase 9: Database Optimization

### New indexes (Alembic migration `a3e1f8b9c012`)
- `ix_dataset_files_uploaded_by` on `dataset_files(uploaded_by)`
- `ix_model_runs_trained_by` on `model_runs(trained_by)`
- `ix_training_jobs_created_at` on `training_jobs(created_at)`
- `ix_training_jobs_active` — partial index on `training_jobs(updated_at) WHERE status IN ('queued', 'running')`

### FK constraints
- `fk_dataset_files_uploaded_by_users` with `ondelete="SET NULL"`
- `fk_model_runs_trained_by_users` with `ondelete="SET NULL"`

### N+1 elimination
Replaced dual COUNT + SELECT queries with single `func.count().over()` window function in 5 endpoints:
- `GET /api/predict/history` (predict.py)
- `GET /api/admin/users` (admin.py)
- `GET /api/data/list` (data.py)
- `GET /api/train/jobs` (train.py)
- `GET /api/model/runs` (model.py)

### Connection pool tuning
```python
pool_size=10, max_overflow=20, pool_timeout=30,
pool_pre_ping=True, pool_recycle=3600
```

---

## Phase 10: API Security Hardening

### Security headers middleware (`main.py`)
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: geolocation=(), microphone=(), camera=(), payment=()`
- `Content-Security-Policy` (default-src 'self', frame-ancestors 'none')
- `Strict-Transport-Security` (production only, 2-year max-age with preload)

### JWT hardening
- `options={"require": ["exp", "sub"]}` on `jwt.decode()` in auth dependency
- Explicit `algorithms=[settings.jwt_algorithm]`

### Password handling
- `SecretStr` type for password fields in `LoginRequest` and `RegisterRequest`
- Password never appears in `repr()`, serialization, or log output
- Accessed via `.get_secret_value()` only at verification/hashing point

### Rate limiting additions
| Endpoint | Limit |
|----------|-------|
| `POST /auth/login` | 5/minute |
| `POST /data/upload` | 5/minute |
| `POST /train/start` | 3/hour |

### CORS hardening
- Wildcard CORS origins rejected at startup in production mode
- Explicit method/header allowlists

### Security tests (`tests/test_security_headers.py`)
8 tests covering: header presence, request IDs, 401 vs 500, invalid JWT, expired JWT, access-as-refresh rejection, viewer role restrictions, cache headers.

---

## Phase 11: Performance Benchmarking

### Lighthouse CI (`.lighthouserc.json`)
- Performance ≥ 0.85 (warn)
- Accessibility ≥ 0.9 (error)
- FCP < 2000ms, LCP < 2500ms, CLS < 0.1

### k6 load testing (`backend/tests/load/k6_smoke.js`)
- Ramp: 0→10 VUs (30s), steady state (1m), ramp down (10s)
- Thresholds: p95 < 500ms, error rate < 1%
- Endpoints tested: login, health, stats, regions, prediction history

### Cache-Control strategy
| Endpoint | TTL | Scope |
|----------|-----|-------|
| `GET /api/regions` | 3600s | public |
| `GET /api/model/info` | 60s | private |
| `GET /api/stats/*` | 300s | private |

---

## Phase 12: Accessibility

- **Skip link**: `<a href="#main-content" class="skip-link">` as first focusable element
- **Main content target**: `id="main-content"` on `<main>` in AppLayout
- **Icon button labels**: `aria-label` on sidebar toggle, dark mode toggle
- **Route announcements**: `aria-live="polite"` div announces page title changes via `ui.routeTitle`
- **SR-only class**: `.sr-only` in main.css for screen-reader-only text
- **Translations**: `a11y.skipToContent` and `a11y.loading` in en.json/sl.json

---

## Phase 13: API Contract Tests

`frontend/src/tests/api/contracts.test.ts` validates 7 domain types:
- `User` — required fields, nullable optionals, role enum
- `TrainingJob` — status enum, progress bounds
- `Dataset` — file metadata fields
- `ModelInfo` — metrics, property types array
- `PredictionResult` — predicted price, used features
- `HealthStatus` — status values (ok/degraded/error)
- `RegionLookup` — municipality and region names

---

## Phase 14: CI/CD & DevOps

### Enhanced GitHub Actions (`.github/workflows/ci.yml`)
- `backend-lint` → `backend-test` → `frontend-lint` → `frontend-test` → `frontend-build` → `e2e-test`
- `security-scan` job via Trivy (CRITICAL + HIGH severity, exit-code 1)
- `docker` job builds and pushes to GHCR on main/tags
- `deploy` job SSHes to VPS for production updates
- Codecov integration for both backend and frontend

### Dependabot (`.github/dependabot.yml`)
- pip (weekly), npm (weekly), Docker (monthly), GitHub Actions (monthly)
- Group updates by ecosystem

### Prometheus monitoring
- `prometheus-fastapi-instrumentator` exposes `/metrics` endpoint
- Graceful fallback if package not installed (warning log, no crash)

---

## Phase 15: E2E Testing (Playwright)

### Configuration (`playwright.config.ts`)
- Test directory: `src/tests/e2e`
- Base URL: `http://localhost:5173`
- webServer: `pnpm dev` auto-started
- Chromium only, 2 retries in CI, screenshot/trace on failure

### Test suites
**auth.spec.ts** (4 tests):
- Login page visibility on unauthenticated access
- Login form has email + password fields
- Error display on invalid credentials
- Skip navigation link presence

**navigation.spec.ts** (4 tests):
- Protected routes redirect to login
- Page title updates on navigation
- Boot loader disappears (no infinite loading)
- No unexpected console errors on login page

### CI integration
E2E job in GitHub Actions installs Playwright + chromium, runs tests, uploads traces on failure (7-day retention).

---

## Files Changed

### New files
| File | Purpose |
|------|---------|
| `frontend/src/types/api.ts` | Domain TypeScript interfaces |
| `frontend/src/stores/tokens.ts` | Module-level reactive token refs |
| `frontend/src/stores/ui.ts` | Route transition state |
| `frontend/src/components/FullPageSpinner.vue` | Global loading overlay |
| `frontend/src/tests/api/contracts.test.ts` | API contract tests |
| `frontend/src/tests/e2e/auth.spec.ts` | Auth E2E tests |
| `frontend/src/tests/e2e/navigation.spec.ts` | Navigation E2E tests |
| `frontend/playwright.config.ts` | Playwright configuration |
| `frontend/.lighthouserc.json` | Lighthouse CI budgets |
| `backend/entrypoint.sh` | Migration + app startup script |
| `backend/tests/test_security_headers.py` | Security header tests |
| `backend/tests/load/k6_smoke.js` | k6 load test script |
| `backend/alembic/versions/a3e1f8b9c012_...` | DB index/FK migration |
| `.github/dependabot.yml` | Dependabot configuration |

### Modified files
| File | Changes |
|------|---------|
| `frontend/vite.config.js` | Env-based proxy, auto-imports, manualChunks |
| `frontend/package.json` | New deps (VueUse, Vitest, Playwright, TS, auto-imports) |
| `frontend/src/App.vue` | Skip link, route transitions, sr announcements |
| `frontend/src/router/index.ts` | UI store hooks, route title announcements |
| `frontend/src/styles/main.css` | Skip-link, sr-only CSS |
| `frontend/src/locales/{en,sl}.json` | a11y translation keys |
| `frontend/src/components/AppLayout.vue` | VueUse, aria-labels, main-content ID |
| `backend/app/main.py` | Security headers, Prometheus, graceful import |
| `backend/app/api/auth.py` | SecretStr password, rate limiting |
| `backend/app/api/{predict,admin,data,train,model}.py` | N+1 fixes, rate limits, cache headers |
| `backend/app/api/regions.py` | Cache-Control header |
| `backend/app/config.py` | CORS wildcard guard |
| `backend/app/database.py` | Connection pool tuning |
| `backend/app/dependencies/auth.py` | JWT decode hardening |
| `backend/app/schemas/auth.py` | SecretStr for passwords |
| `backend/app/models/{dataset,model_run,training_job}.py` | FK constraints, indexes |
| `backend/pyproject.toml` | prometheus dep, pytest config, coverage config |
| `.github/workflows/ci.yml` | E2E, security scan, coverage jobs |
| `docker-compose.yml` | VITE_API_URL env, entrypoint |

---

## Dependencies Added

### Frontend (runtime)
```
@vueuse/core ^14.0.0
```

### Frontend (dev)
```
vitest ^4.1.0
@vitest/ui ^4.1.0
@vitest/coverage-v8 ^4.1.0
@vue/test-utils ^2.4.6
happy-dom ^20.0.0
typescript ^5.7.0
vue-tsc ^3.0.0
@types/node ^25.0.0
@types/leaflet ^1.9.14
unplugin-vue-components ^31.0.0
unplugin-auto-import ^21.0.0
@primevue/auto-import-resolver ^4.5.4
@playwright/test ^1.52.0
```

### Backend (runtime)
```
prometheus-fastapi-instrumentator >=7.0.0
```

### Backend (dev)
```
aiosqlite >=0.20.0
```

---

## Verification

```bash
# Backend tests
cd backend && pytest -v --cov=app --cov-report=term

# Frontend unit tests
cd frontend && pnpm test

# TypeScript check
cd frontend && pnpm exec vue-tsc --noEmit

# Frontend build
cd frontend && pnpm build

# E2E tests (requires running frontend + backend)
cd frontend && pnpm test:e2e

# Security headers
curl -sI http://localhost:8000/api/health | grep -i "x-content-type-options\|x-frame-options\|x-request-id"

# Prometheus metrics
curl -s http://localhost:8000/metrics | head -5
```
