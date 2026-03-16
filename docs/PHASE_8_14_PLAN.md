# Phase 8–14 — v0.8.4–v0.8.10 Upgrade & Improvement Plan

> Comprehensive upgrade from v1 feature parity analysis, powered by [Agency Agents](https://github.com/msitarzewski/agency-agents).

| Item | Value |
|------|-------|
| **Current Version** | 0.8.3 |
| **Target Version** | 0.8.10 |
| **Scope** | ML bug fixes, feature parity, performance, security, UX, accessibility, testing, documentation |
| **Method** | Agency agent-driven analysis and implementation across 7 phases |

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
- [ ] Group medians computed from train split only
- [ ] Preprocessor fitted once during warm-start loop
- [ ] Map transactions return WGS84 coordinates (~46.x lat, ~14.x lon for Slovenia)
- [ ] All CC-SI codes correctly classified
- [ ] Municipality code-based region lookup works
- [ ] Combined metrics reported in training results

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
- [ ] Score listings response includes all original fields
- [ ] Stats overview returns min/max/std price and year_built stats
- [ ] Region stats include min/max price
- [ ] Diagnostics include train/test rows and used_features
- [ ] Frontend views display enriched data

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
- [ ] Map transactions endpoint is significantly faster
- [ ] Redis cache helpers deduplicated
- [ ] No code quality issues remain

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
- [ ] CSP headers present in responses
- [ ] All inputs validated
- [ ] No internal paths or stack traces in error responses
- [ ] No known vulnerable dependencies

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
- [ ] All pages pass WCAG AA contrast requirements
- [ ] Tab navigation reaches all interactive elements
- [ ] Screen reader can navigate all pages
- [ ] Forms show clear validation errors
- [ ] All pages have loading and error states

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
- [ ] All new tests pass
- [ ] Total test count increased from 111
- [ ] No regressions in existing tests

---

## Phase 14 — Documentation & Final Polish (v0.8.10)

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
- [ ] All docs reflect v0.8.10
- [ ] No stale version references
- [ ] All new features documented
- [ ] API reference complete
- [ ] Final manual verification passes

---

## Phase Progress

| Phase | Description | Version | Status |
|-------|-------------|---------|--------|
| Phase 8 | Critical ML & Data Fixes | v0.8.4 | ✅ Complete |
| Phase 9 | Feature Parity & API Completeness | v0.8.5 | 🔄 In Progress |
| Phase 10 | Backend Performance & Code Quality | v0.8.6 | ⬜ Pending |
| Phase 11 | Security Hardening | v0.8.7 | ⬜ Pending |
| Phase 12 | Frontend UX & Accessibility | v0.8.8 | ⬜ Pending |
| Phase 13 | Testing Expansion | v0.8.9 | ⬜ Pending |
| Phase 14 | Documentation & Final Polish | v0.8.10 | ⬜ Pending |
