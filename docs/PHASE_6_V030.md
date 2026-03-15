# Phase 6 — v0.3.0 Hardening & Polish

> Security hardening, backend robustness, frontend accessibility, expanded test coverage, and i18n completion.

| Item | Value |
|------|-------|
| **Version** | 0.3.0 |
| **Previous** | 0.2.5 |
| **Scope** | Security, backend infra, frontend UX, testing, i18n |

---

## Phase 6.1 — Security Hardening

### Changes
- Rate limiting on auth endpoints via slowapi (5 req/min per IP)
- Token blacklist for logout — invalidated tokens stored in Redis
- Security response headers: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`
- Input range validation on prediction requests using Pydantic `Field` constraints
- Fixed silent exception swallowing — replaced bare `except` with specific exception types + logging

### Files Modified
- `backend/app/main.py` — slowapi middleware, security headers middleware
- `backend/app/api/auth.py` — rate limiter decorators, token blacklist on logout
- `backend/app/api/predict.py` — Pydantic Field constraints on request schema
- `backend/app/schemas/predict.py` — input validation ranges
- `backend/app/services/ml.py` — specific exception handling
- `backend/app/tasks/train.py` — specific exception handling
- `backend/pyproject.toml` — added `slowapi>=0.1.9` dependency

### Verification
- [x] Rate limiter returns 429 after 5 rapid login attempts
- [x] Logout invalidates token (subsequent requests return 401)
- [x] Security headers present in all responses
- [x] Prediction rejects out-of-range values with 422
- [x] No bare `except:` clauses remain in backend

---

## Phase 6.2 — ML Improvement

### Changes
- Replaced built-in `feature_importances_` with permutation importance (`sklearn.inspection.permutation_importance`, `n_repeats=3`)
- Permutation importance computed on test set for unbiased out-of-sample scores
- Falls back to built-in importances if permutation step fails

### Files Modified
- `backend/app/services/ml.py` — permutation importance computation
- `backend/app/api/model.py` — importance endpoint returns updated scores

### Verification
- [x] Feature importance values differ from built-in (more reliable)
- [x] Fallback works when test set is too small
- [x] `/api/model/importance` returns correct structure

---

## Phase 6.3 — Backend Infrastructure

### Changes
- Structured request logging middleware with correlation IDs (`X-Request-ID` header)
- Global exception handler — returns structured JSON errors, no stack trace leaks in production
- Production-grade logging config (JSON format in prod, human-readable in dev)
- Redis caching for stats and model info endpoints (5-min TTL)
- Pagination support for datasets, prediction history, training jobs, model runs
- Enhanced health check — reports DB, Redis, and model availability
- GZip compression middleware for response compression
- Database indexes on `prediction_logs` and `model_runs` tables

### Files Modified
- `backend/app/main.py` — middleware registration (logging, gzip, exception handler)
- `backend/app/middleware/` — request logging, correlation ID injection
- `backend/app/api/stats.py` — Redis caching decorators
- `backend/app/api/model.py` — Redis caching, pagination params
- `backend/app/api/data.py` — pagination params
- `backend/app/api/predict.py` — pagination on history endpoint
- `backend/app/api/train.py` — pagination on jobs endpoint
- `backend/app/api/health.py` — enhanced health check (DB + Redis + model)
- `backend/app/config.py` — logging configuration
- `backend/alembic/versions/` — migration for database indexes

### Verification
- [x] `X-Request-ID` header in all responses
- [x] Error responses are JSON with `detail` field, no tracebacks
- [x] Stats endpoints return cached results on second call (5-min TTL)
- [x] Pagination params (`skip`, `limit`) work on list endpoints
- [x] `/api/health` returns `db`, `redis`, `model` status fields
- [x] Gzip compression active on large responses

---

## Phase 6.4 — Testing Expansion

### Changes
- Expanded from 14 to 96 tests
- Coverage across all endpoint groups: auth, data, predict, train, model, stats, admin, analysis, regions
- Added `test_model.py` with synthetic data tests for ML pipeline

### Files Modified
- `backend/tests/test_auth.py` — authentication flow tests
- `backend/tests/test_data.py` — dataset CRUD tests
- `backend/tests/test_predict.py` — prediction endpoint tests
- `backend/tests/test_train.py` — training job tests
- `backend/tests/test_model.py` — ML model tests (synthetic CSV)
- `backend/tests/test_stats.py` — statistics endpoint tests
- `backend/tests/test_admin.py` — admin user management tests
- `backend/tests/test_analysis.py` — listing analysis tests
- `backend/tests/test_regions.py` — region/municipality tests
- `backend/tests/conftest.py` — shared fixtures

### Verification
- [x] `pytest -v` passes all 96 tests
- [x] No tests require real database or model artifacts

---

## Phase 6.5 — Frontend UX & Accessibility

### Changes
- Dark mode with system preference detection (`prefers-color-scheme`) and localStorage persistence
- Mobile responsive layout with hamburger menu and collapsible sidebar
- WCAG AA contrast fix for sidebar text colors
- Loading spinner component (`LoadingSpinner.vue`) for async operations
- Empty state component (`EmptyState.vue`) for zero-data views
- Toast notification system (`ToastContainer.vue`) for API error feedback
- Inline form validation on PredictionView and LoginView
- ARIA labels and `role` attributes on interactive elements
- Keyboard navigation improvements
- Axios request timeout set to 30 seconds

### Files Modified
- `frontend/src/components/AppLayout.vue` — dark mode toggle, mobile menu, ARIA labels
- `frontend/src/components/LoadingSpinner.vue` — new component
- `frontend/src/components/EmptyState.vue` — new component
- `frontend/src/components/ToastContainer.vue` — new component
- `frontend/src/composables/useDarkMode.js` — dark mode composable
- `frontend/src/composables/useToast.js` — toast notification composable
- `frontend/src/composables/useApi.js` — axios timeout, error toast integration
- `frontend/src/views/LoginView.vue` — inline validation
- `frontend/src/views/PredictionView.vue` — inline validation
- `frontend/src/views/DataView.vue` — loading spinner, empty state
- `frontend/src/views/AdminView.vue` — loading spinner
- `frontend/src/views/DashboardView.vue` — loading spinner
- `frontend/src/views/MapView.vue` — loading spinner
- `frontend/src/styles/main.css` — dark mode CSS variables, responsive breakpoints

### Verification
- [x] Dark mode toggles correctly and persists across page reload
- [x] System dark mode preference detected on first visit
- [x] Mobile layout renders hamburger menu at ≤768px
- [x] Sidebar text meets WCAG AA contrast ratio (4.5:1)
- [x] Loading spinners shown during API calls
- [x] Empty states shown when no data available
- [x] Toast notifications appear on API errors
- [x] Form validation errors shown inline before submission
- [x] All interactive elements have ARIA labels

---

## Phase 6.6 — i18n Completion

### Changes
- Fixed hardcoded Slovenian string in `App.vue` loading state
- Fixed hardcoded English role toggle labels in `AdminView.vue`
- Added missing locale keys for both `sl.json` and `en.json`:
  - `common`: close, success, warning, info, retry, yes, no, actions, back, next
  - `admin`: makeAdmin, makeViewer
  - `empty`: noUsers, noTrainingJobs
  - `validation`: invalidEmail, minPassword, minValue, maxValue
  - `error`: network, unauthorized, forbidden, notFound, server, timeout, rateLimited
  - `health`: status, healthy, unhealthy, database, redis, model
  - `pagination`: page, of, perPage, next, previous

### Files Modified
- `frontend/src/App.vue` — replaced hardcoded `Nalaganje...` with `$t('common.loading')`
- `frontend/src/views/AdminView.vue` — replaced hardcoded `→ viewer` / `→ admin` with i18n calls
- `frontend/src/locales/sl.json` — 30+ new keys added
- `frontend/src/locales/en.json` — 30+ new keys added

### Verification
- [x] No hardcoded user-facing strings in Vue templates
- [x] Both locale files have identical key structures
- [x] All new keys have proper Slovenian and English translations
- [x] Frontend builds without errors

---

## Phase 6.7 — Version & Documentation

### Changes
- Version bumped to 0.3.0 across all config files
- Full v0.3.0 changelog in `docs/MASTER.md`
- Updated `README.md` with new features, test count, tech stack
- Created `docs/PHASE_6_V030.md` (this file)

### Files Modified
- `backend/pyproject.toml` — version 0.3.0
- `frontend/package.json` — version 0.3.0
- `backend/app/config.py` — APP_VERSION 0.3.0
- `.env.example` — APP_VERSION 0.3.0
- `README.md` — updated features, tech stack, test count
- `docs/MASTER.md` — full v0.3.0 changelog, slowapi in tech stack

### Verification
- [x] `grep -r "0.2.5"` returns no version references (except changelog history)
- [x] All 4 config files show 0.3.0
- [x] README accurately reflects current feature set
- [x] MASTER.md changelog covers all phases
