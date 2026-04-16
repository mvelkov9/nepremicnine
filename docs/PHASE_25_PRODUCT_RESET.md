# Phase 25 - Product UX Reset and Proof Workflow (v0.15.0)

## Summary

Phase 25 turns the frontend modernization plan into a concrete product release instead of a loose styling pass.

The work focused on four areas:

1. A dedicated "model vs GURS" proof workflow for both viewers and admins
2. PrimeVue v4 cleanup and table standardization
3. Better request behavior through caching and stale-request cancellation
4. Navigation and shell cleanup so utilities stop competing with the main product

## Delivered

### 1. Benchmark / proof workflow

- Added `GET /api/model/benchmark/gurs-summary`
- Added `GET /api/model/benchmark/gurs-transactions`
- Added shared benchmark schemas and TypeScript types
- Added viewer route `/dokaz`
- Added admin route `/admin/dokaz`
- Added a dedicated proof page showing:
  - shared-coverage metrics
  - model vs GURS deltas
  - segment winners
  - transaction-level drilldown for admins
  - CSV export for the proof table

This makes the "we beat GURS" claim inspectable instead of hiding it inside diagnostics aggregates.

### 2. Server-side table patterns

- Added `useServerTableState.ts` for reusable route-synced table state
- Converted benchmark transactions to server pagination, sorting, and search
- Converted admin users to server pagination, sorting, filtering, and search
- Converted the dataset library to a real server-driven table instead of client-side filtering over a paged response
- Extended backend list endpoints to return a consistent table envelope:
  - `page`
  - `per_page`
  - `page_size`
  - `pages`
  - `filters`
  - `sort`
  - `order`

### 3. Performance and data flow

- Added a shared reference-data cache store for municipalities, regions, property types, and years
- Reused that cache in dashboard, market, regions, municipalities, map, prediction, and analysis views
- Added stale-request cancellation in the stats store so rapid filter changes do not render old explorer responses
- Removed wasteful admin-home fetching of the full user list just to count users
- Tightened dataset-table request deduplication so only identical in-flight requests are shared

### 4. UX and visual system

- Removed deprecated `TabView` usage from the main viewer explorer pages
- Demoted `Ukazi`, `Pladenj`, and `Aktivnosti` into a cleaner workspace entry in the shell
- Refreshed the login/landing experience
- Added clearer light/dark table, tab, and focus styling
- Added benchmark links from the dashboard and diagnostics so the proof workflow is discoverable

## Key Files

- `backend/app/api/model.py`
- `backend/app/services/model_service.py`
- `backend/app/api/admin.py`
- `backend/app/api/data.py`
- `frontend/src/views/BenchmarkView.vue`
- `frontend/src/views/AdminView.vue`
- `frontend/src/views/DataView.vue`
- `frontend/src/stores/referenceData.ts`
- `frontend/src/stores/stats.ts`
- `frontend/src/composables/useServerTableState.ts`
- `frontend/src/styles/main.css`
- `frontend/src/theme/preset.js`

## Verification

- Python compile checks passed for the touched backend modules
- Locale JSON validation passed
- No `TabView` imports remain in `frontend/src`

## Remaining follow-up

Phase 25 ships the product reset foundation, but there is still room to keep iterating:

- deeper decomposition of the largest admin views (`PrepareView`, `ModelView`, `DiagnosticsView`)
- broader automated frontend verification once Node/pnpm are available in the execution environment
- optional package-audit cleanup and dependency refreshes with the local JS toolchain
