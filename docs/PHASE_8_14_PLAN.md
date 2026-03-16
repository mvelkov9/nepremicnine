# Phase 8–17 — v0.8.4–v0.8.13 Upgrade & Improvement Plan

> Comprehensive upgrade from v1 feature parity analysis, powered by [Agency Agents](https://github.com/msitarzewski/agency-agents).

| Item | Value |
|------|-------|
| **Current Version** | 0.8.13 |
| **Target Version** | 0.8.13 |
| **Scope** | ML bug fixes, feature parity, performance, security, UX, accessibility, testing, documentation |
| **Method** | Agency agent-driven analysis and implementation across 7 phases |

---

## Post-Plan Addendum — Analytical Portal Expansion

After shipping the original `v0.8.13` bugfix/docs/favicon/training/data-prep work, the authenticated product layer was expanded with a second wave focused on analytical discovery and AVM context.

### Delivered

1. **Backend stats expansion**
   - Added `GET /api/stats/market-home`
   - Added `GET /api/stats/municipality/{slug}`
   - Added `GET /api/stats/comparables`
   - Added shared municipality slug normalization helper
   - Extended `GET /api/stats/municipalities-by-region` with optional `region=` filtering for map workflows
2. **Frontend product expansion**
   - Added new authenticated route `/obcine/:slug`
   - Extended stats store with `marketHome`, `municipalityDetail`, and `comparables`
   - Rebuilt Dashboard into a market-intelligence landing page
   - Rebuilt Prediction into a two-column AVM flow with municipality context and comparable transactions
   - Rebuilt Map into a denser explorer with municipality drill-down and valuation handoff
3. **Shell consistency**
   - Refined the authenticated shell to better frame analytical workflows without changing the auth or deployment model

### Verification Snapshot

- `ruff check` on touched backend files passes
- frontend `eslint` passes on touched shell/router/store/views
- frontend `prettier --check` passes on touched files
- `vite build` passes
- targeted backend `pytest` still times out inside the existing harness, so endpoint coverage for this addendum is documented but not fully executable in the current local test setup

---

## Gap Analysis Summary (v1 → v2)

A thorough comparison of the v1 app (`Nepremicnine v3.5`, Flask/SQLite) with the v2 app (`nepremicnine-v2 v0.8.3`, FastAPI/PostgreSQL) revealed the following critical gaps:

| # | Issue | Severity | Phase |
|---|-------|----------|-------|
| 1 | Data leakage: group medians computed before train/test split | **Critical** | 8 |
| 2 | Warm-start loop re-fits entire pipeline (incl. TargetEncoder) each iteration | **Critical** | 8 |
| 3 | D96/TM → WGS84 coordinate conversion missing from map-transactions | **Critical** | 8 |
| 4 | 9 CC-SI property type prefix mappings missing | **High** | 8 |
| 5 | Region lookup by municipality code (sifra) lost | **High** | 8 |
| 6 | No combined routing metrics reported after training | **Medium** | 8 |
| 7 | Score listings response missing original listing fields | **Medium** | 9 |
| 8 | Stats overview missing fields (min/max/std, year_built, region count) | **Medium** | 9 |
| 9 | Model diagnostics missing fields (train/test rows, used_features, model_type) | **Medium** | 9 |
| 10 | Map transactions uses slow `iterrows()` instead of vectorized pandas | **Medium** | 10 |

---

## Phase 8 — Critical ML & Data Fixes (v0.8.4)

**Agents**: Backend Architect, Code Reviewer

### Changes

1. **Fix data leakage in group medians** — move `price_per_m2_region` and `price_per_m2_type` computation to AFTER `train_test_split()`, compute only from training set
2. **Fix warm-start pipeline re-fitting** — separate preprocessor `.fit_transform()` from regressor warm-start loop; fit preprocessor once, then warm-start only the regressor on transformed data
3. **Add D96/TM → WGS84 coordinate conversion** — port the vectorized numpy conversion from v1 to the `/stats/map-transactions` endpoint
4. **Add 9 missing CC-SI property type prefix mappings** — add codes 1200, 1241, 1262, 1263, 1264, 1265, 1272, 1280, 1290 to `_CC_SI_PREFIX_MAP`
5. **Add region lookup by municipality code (sifra)** — implement `lookup_region_by_code()` in regions_service.py, use during ETN enrichment when RPE_OBCINE_SIFRA is available
6. **Add combined routing metrics** — after training per-type + global models, compute combined test set metrics using the per-type routing system

### Files Modified
- `backend/app/services/model_service.py`
- `backend/app/services/data_processing_service.py`
- `backend/app/services/regions_service.py`
- `backend/app/api/stats.py`

### Verification
- [x] Group medians computed from train split only
- [x] Preprocessor fitted once during warm-start loop
- [x] Map transactions return WGS84 coordinates (~46.x lat, ~14.x lon for Slovenia)
- [x] All CC-SI codes correctly classified
- [x] Municipality code-based region lookup works
- [x] Combined metrics reported in training results

---

## Phase 9 — Feature Parity & API Completeness (v0.8.5)

**Agents**: Backend Architect, Software Architect

### Changes

1. **Enrich score_listings response** — include original listing fields (municipality, property_type, size_m2, etc.) in ScoredListing response
2. **Enhance stats overview** — add price min/max/std, year_built stats, region count, available data years
3. **Add stats regions min/max price** — include min_price and max_price per region
4. **Enhance model diagnostics** — add train_rows, test_rows, used_features, model_type, dual importance (gini + permutation)
5. **Update frontend** — update AnalysisView to display enriched listing fields, update DashboardView for new stats fields

### Files Modified
- `backend/app/api/analysis.py`
- `backend/app/api/stats.py`
- `backend/app/api/model.py`
- `backend/app/services/model_service.py`
- `frontend/src/views/AnalysisView.vue`
- `frontend/src/views/DashboardView.vue`
- `frontend/src/locales/sl.json`
- `frontend/src/locales/en.json`

### Verification
- [x] Score listings response includes all original fields
- [x] Stats overview returns min/max/std price and year_built stats
- [x] Region stats include min/max price
- [x] Diagnostics include train/test rows and used_features
- [x] Frontend views display enriched data

---

## Phase 10 — Backend Performance & Code Quality (v0.8.6)

**Agents**: Database Optimizer, Performance Benchmarker, Code Reviewer

### Changes

1. **Vectorize map-transactions** — replace `iterrows()` with `df.to_dict(orient="records")` for 10-100x speedup
2. **DRY up Redis cache helpers** — extract shared `cache_get`/`cache_set` into `app/utils/cache.py`
3. **Code quality improvements** — fix any issues found during code review
4. **Optimize stats endpoints** — review and optimize pandas groupby operations

### Files Modified
- `backend/app/api/stats.py`
- `backend/app/api/model.py`
- `backend/app/utils/cache.py` (new)

### Verification
- [x] Map transactions endpoint is significantly faster
- [x] Redis cache helpers deduplicated
- [x] No code quality issues remain

---

## Phase 11 — Security Hardening (v0.8.7)

**Agents**: Security Engineer

### Changes

1. **CSP headers** — add Content-Security-Policy header
2. **Input validation audit** — review all endpoints for edge cases
3. **File upload security** — review size limits, type validation, path handling
4. **Error handling audit** — ensure no internal details leak in error responses
5. **Dependency security** — check for known vulnerabilities

### Files Modified
- `backend/app/main.py`
- `backend/app/api/*.py` (as needed)
- `frontend/nginx.conf`

### Verification
- [x] CSP headers present in responses
- [x] All inputs validated
- [x] No internal paths or stack traces in error responses
- [x] No known vulnerable dependencies

---

## Phase 12 — Frontend UX & Accessibility (v0.8.8)

**Agents**: Frontend Developer, UX Architect, Accessibility Auditor

### Changes

1. **WCAG AA audit** — review all pages for contrast, semantic HTML, focus management
2. **Keyboard navigation** — ensure all interactive elements are keyboard-accessible
3. **ARIA labels** — add missing roles, labels, and live regions
4. **Form validation UX** — improve inline validation messages and error states
5. **Loading/error states** — ensure consistent feedback across all views
6. **Responsive design** — review breakpoints and mobile layouts

### Files Modified
- `frontend/src/views/*.vue`
- `frontend/src/components/*.vue`
- `frontend/src/styles/main.css`
- `frontend/src/locales/sl.json`
- `frontend/src/locales/en.json`

### Verification
- [x] All pages pass WCAG AA contrast requirements
- [x] Tab navigation reaches all interactive elements
- [x] Screen reader can navigate all pages
- [x] Forms show clear validation errors
- [x] All pages have loading and error states

---

## Phase 13 — Testing Expansion (v0.8.9)

**Agents**: API Tester

### Changes

1. **Tests for Phase 8 fixes** — data leakage prevention, coordinate conversion, CC-SI mapping, region sifra lookup
2. **Tests for Phase 9 features** — enriched score listings, enhanced stats/diagnostics
3. **Edge case tests** — empty datasets, invalid inputs, boundary values
4. **Security tests** — auth bypass attempts, input injection, rate limit verification

### Files Modified
- `backend/tests/test_model.py` (new/expanded)
- `backend/tests/test_data_processing.py` (new/expanded)
- `backend/tests/test_stats.py` (expanded)
- `backend/tests/test_analysis.py` (expanded)
- `backend/tests/test_regions.py` (expanded)

### Verification
- [x] All new tests pass
- [x] Total test count increased from 111 to 126
- [x] No regressions in existing tests

---

## Phase 14 — Documentation & Final Polish (v0.8.10)
## Phase 15 — CI/CD & Production Fix (v0.8.11)

**Agents**: DevOps

### Changes

1. **Backend lint/format** — fixed 4 unused imports (ruff check) + 3 files reformatted (ruff format)
2. **Frontend format** — fixed 5 Vue files with Prettier style violations
3. **Production version fix** — `APP_VERSION=0.1.1` in VPS `.env` was overriding the code default; updated to `0.8.11`
4. **Version bump** — all version references updated to 0.8.11

### Files Modified
- `backend/tests/test_security.py` — removed unused imports
- `backend/tests/test_stats.py` — removed unused imports
- `backend/app/main.py` — reformatted
- `backend/tests/test_data.py` — reformatted
- `backend/tests/test_stats.py` — reformatted
- `frontend/src/views/AdminView.vue` — Prettier format
- `frontend/src/views/DataView.vue` — Prettier format
- `frontend/src/views/LoginView.vue` — Prettier format
- `frontend/src/views/PredictionView.vue` — Prettier format
- `frontend/src/views/PrepareView.vue` — Prettier format
- `backend/app/config.py` — version → 0.8.11
- `backend/pyproject.toml` — version → 0.8.11
- `frontend/package.json` — version → 0.8.11
- `.env.example` — APP_VERSION → 0.8.11
- VPS `/root/nepremicnine/.env` — APP_VERSION → 0.8.11

### Verification
- [x] `ruff check .` passes (0 errors)
- [x] `ruff format --check .` passes (58 files formatted)
- [x] `pnpm format:check` passes
- [x] `pnpm lint` passes
- [x] `pnpm build` succeeds
- [x] VPS `.env` APP_VERSION updated to 0.8.11

---



**Agents**: Technical Writer

### Changes

1. **Phase 8-14 changelog doc** — comprehensive doc covering all changes
2. **Update MASTER.md** — version, phase table, changelog entries
3. **Update README.md** — version, features, API endpoints, test count
4. **Update DEPLOYMENT.md** — any new configuration requirements
5. **Final bug check** — verify all features work end-to-end

### Files Modified
- `docs/PHASE_8_14_PLAN.md` → `docs/PHASE_8_14_V084_V0810.md` (rename and fill verification)
- `docs/MASTER.md`
- `README.md`
- `docs/DEPLOYMENT.md`

### Verification
- [x] All docs reflect v0.8.11
- [x] No stale version references
- [x] All new features documented
- [x] API reference complete
- [x] Final manual verification passes

---

## Phase 16 — Workflow & UX Repair (v0.8.12)

**Agents**: Frontend Developer, Backend Architect, DevOps Automator, Technical Writer

### Changes

1. **Prepared dataset visibility** — added `/api/data/training-dataset` and returned relative dataset paths so the frontend can guide users from preparation to training cleanly
2. **Model workflow clarity** — Model view now recommends the prepared dataset, shows the current model source, and keeps uploaded CSVs as fallback sources
3. **Profile personalization** — added `PATCH /api/auth/me` with editable name and optional avatar URL, surfaced via the new profile panel in the app shell
4. **Production fixes** — app version now stays visible in production health checks, nginx upload limit raised to 1024 MB, and `/favicon.ico` falls back to `/favicon.svg`
5. **UI refresh** — redesigned login, app shell, dashboard, and training flow to make the product feel less barren and more intentional

## Phase 17 — Training Recovery & Data Visibility (v0.8.13)

### Changes

1. **Training recovery** — added `/api/train/active`, surfaced active job context in 409 responses, and taught the frontend to resume polling queued/running jobs after refresh instead of appearing broken
2. **Stale training cleanup** — queued/running jobs that lose their Redis state are now marked failed once stale, so they do not block future training attempts indefinitely
3. **Dataset visibility** — frontend dataset loading now fetches every paginated page, which prevents older ETN year pairs such as 2024 from disappearing from bulk preparation
4. **Safer ETN bulk combine** — multi-year preparation now returns `per_year` counts and deduplicates using stable source row keys instead of coarse feature columns that could remove valid rows
5. **Production favicon bundle** — added real `favicon.ico`, `favicon-32x32.png`, and `apple-touch-icon.png` assets and updated nginx/icon links for better browser compatibility
6. **Version bump** — app/config/docs updated to 0.8.13
6. **i18n completion** — mapped common backend error messages into localized frontend messages for both Slovenian and English

### Verification

- [x] Frontend ESLint completes without errors
- [x] Frontend Prettier check passes
- [x] Frontend production build succeeds
- [x] Backend Ruff lint passes
- [x] Backend Ruff format check passes
- [x] Python source compiles successfully (`compile(...)` smoke check)
- [ ] Full backend pytest suite
  Note: blocked in this sandbox because the async SQLite layer hangs during connection setup before tests execute

---

## Phase Progress

| Phase | Description | Version | Status |
|-------|-------------|---------|--------|
| Phase 8 | Critical ML & Data Fixes | v0.8.4 | ✅ Complete |
| Phase 9 | Feature Parity & API Completeness | v0.8.5 | ✅ Complete |
| Phase 10 | Backend Performance & Code Quality | v0.8.6 | ✅ Complete |
| Phase 11 | Security Hardening | v0.8.7 | ✅ Complete |
| Phase 12 | Frontend UX & Accessibility | v0.8.8 | ✅ Complete |
| Phase 13 | Testing Expansion | v0.8.9 | ✅ Complete |
| Phase 14 | Documentation & Final Polish | v0.8.10 | ✅ Complete |
| Phase 15 | CI/CD & Production Fix | v0.8.11 | ✅ Complete |
| Phase 16 | Workflow & UX Repair | v0.8.12 | ✅ Complete |
| Phase 17 | Training Recovery & Data Visibility | v0.8.13 | ✅ Complete |
