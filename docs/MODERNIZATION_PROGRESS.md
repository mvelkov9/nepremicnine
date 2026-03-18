# Modernization Progress

Last updated: 2026-03-18

## Completed

### Phase 1: Runtime Stability and Faster Local Dev

- Added mtime-aware model artifact reloading so API processes do not keep serving stale models after retraining.
- Added explicit region cache invalidation after RPE/RN imports.
- Changed upload handling to stream files to disk in chunks instead of reading entire uploads into memory.
- Offloaded selected heavy synchronous backend work to threads in data preparation, prediction, and analysis endpoints.
- Made the frontend Vite API proxy configurable through `VITE_API_PROXY_TARGET`.
- Removed the forced frontend `pnpm install` from every Docker dev container start.
- Added frontend test foundations with Vitest, Vue Test Utils, jsdom, and an initial passing unit test.
- Split frontend lint into `lint` and `lint:fix`.
- Excluded generated `.nuxt-verify-build/` artifacts from frontend linting.
- Documented the recommended hybrid local workflow in the README.

### Dependency Modernization

- Upgraded the requested frontend packages to their latest available versions:
	- `@vitejs/plugin-vue` → `6.0.5`
	- `@vueuse/core` → `14.2.1`
	- `eslint` → `10.0.3`
	- `eslint-plugin-vue` → `10.8.0`
	- `jsdom` → `29.0.0`
	- `pinia` → `3.0.4`
	- `vite` → `8.0.0`
	- `vitest` → `4.1.0`
	- `vue-i18n` → `11.3.0`
	- `vue-router` → `5.0.3`
- Added `vue-eslint-parser` `10.4.0` explicitly to satisfy the upgraded ESLint Vue plugin peer dependency.

### Frontend Shell and Auth Bootstrap

- Added a shared Pinia instance export so router guards and app boot logic use the same store container.
- Added a dedicated UI state store for bootstrap and navigation loading state.
- Refactored auth initialization into a deduplicated `init()` flow with an explicit `initialized` flag.
- Moved session persistence in the auth store to VueUse local-storage bindings.
- Changed router guards to await auth initialization before protected-route decisions.
- Added a global fullscreen boot loader and a route-transition overlay loader.
- Simplified `App.vue` so the app shell renders only after auth bootstrap completes.
- Switched sidebar collapse persistence in the shell to VueUse storage.
- Added auth-store regression tests covering initialization and deduplicated bootstrap calls.

### Feedback Layer Modernization

- Replaced the custom toast container implementation with PrimeVue ToastService-backed notifications.
- Added a shared PrimeVue confirmation-dialog bridge for promise-based confirms in setup code.
- Registered PrimeVue ToastService and ConfirmationService at app boot.
- Replaced native `confirm()` usage in admin user deletion and dataset deletion flows.
- Added global styling for PrimeVue toast and confirmation overlays so they match the existing shell visual system.

### Admin Surface Modernization

- Rebuilt `AdminView` around the shared app primitives: `PageHeader`, `MetricCard`, `DataTable`, `Tag`, and `EmptyState`.
- Added success toasts for user role changes, activation changes, and deletions.
- Added summary metrics for total users, admins, viewers, and active accounts.
- Extended `DataView` so upload and delete actions now produce consistent success toasts in addition to confirmation dialogs.
- Added matching locale strings for the new admin and data feedback states in both Slovenian and English.

### Map and Viewer Performance

- Refactored `MapView` to centralize active filter params instead of rebuilding request params in multiple fetch paths.
- Added debounced filter watching so rapid map filter changes do not trigger a full API refetch on every single input mutation.
- Added cancellation for in-flight map data requests, preventing stale responses from repainting the map after newer filters are applied.
- Added cancellation for in-flight comparable-transaction detail requests in the map detail dialog.
- Synced active map filters back into the route query so the current exploration state is stable and shareable.
- Reset invalid municipality selections when the selected region changes and the municipality no longer belongs to the current filter scope.

### Prediction, Analysis, and Shared API Flow

- Added a shared municipality-lookup composable with cached loading and shared autocomplete behavior for viewer pages.
- Hardened the frontend API client with single-flight token refresh so concurrent 401 responses do not trigger multiple refresh attempts.
- Added per-request opt-out for global error toasts, allowing pages with inline error states to avoid duplicate feedback.
- Updated the stats store so comparable and municipality detail requests can receive cancellation signals and silent-request flags.
- Refactored `PredictionView` to share municipality lookup logic, cancel stale context requests, sync key inputs into the route query, and clear stale estimates when the subject changes.
- Removed the misleading query-prefill behavior that could display a non-model price as if it were a fresh prediction result.
- Added clearer prediction result summary metrics for predicted price per m², municipality median price, and comparable count.
- Refactored `AnalysisView` to share municipality lookup logic, validate guided inputs before scoring, show explicit loading and empty states, and surface summary counts for total, over-, under-, and market-aligned listings.
- Added consistent success toasts for completed prediction and analysis actions, with matching English and Slovenian locale copy.

### Diagnostics, Model Admin UX, and Bundle Splitting

- Rebuilt `DiagnosticsView` around the shared page primitives (`PageHeader`, `MetricCard`, `LoadingSpinner`, `EmptyState`) instead of the older one-off layout.
- Added a diagnostics-specific loading state so the page no longer flashes an empty “no model” state while model metadata is still loading.
- Added clearer diagnostics section copy for the current model snapshot, routing summary, chart comparisons, top features, and detailed type/region tables.
- Added a success toast when a new training job is accepted from `ModelView`.
- Added a page-level loading state to `ModelView` so the training/admin surface does not render half-initialized data while all model datasets and job history are still loading.
- Added explicit Rollup manual chunking in Vite to separate map, charting, PrimeVue data-table, PrimeVue form UI, core Vue stack, and utility libraries into more predictable build outputs.

### Shared Table Migration and Bundle Reduction

- Added a shared lightweight `AppDataTable` component for sortable, paginated table rendering without the PrimeVue data-table stack.
- Migrated `AdminView`, `DataView`, `ModelView`, `AnalysisView`, `DashboardView`, and `MapView` away from PrimeVue `DataTable` and `Column` to the shared table primitive.
- Removed the last frontend imports of PrimeVue's data-table components so the previous `prime-data` bundle is no longer emitted in production builds.
- Kept custom table formatting through slot-based cells so admin and viewer pages still support labels, badges, actions, and numeric formatting without the heavier dependency.

## Validated

- Backend targeted regression tests pass.
- Frontend Vitest passes.
- Frontend lint passes.
- Frontend production build passes.
- Auth bootstrap regression tests pass on the upgraded frontend stack.
- PrimeVue feedback-layer changes pass lint, tests, and production build.
- AdminView and DataView modernization changes pass lint, tests, and production build.
- MapView performance refactor passes lint, tests, and production build.
- Prediction, Analysis, and shared API flow changes pass lint, tests, and production build.
- Diagnostics, Model admin UX, and bundle-splitting changes pass lint, tests, and production build.
- Shared table migration and remaining bundle-reduction changes pass lint, tests, and production build.

## In Progress

### Next Frontend Slice

- Start app-shell visual cleanup and shared layout primitives.
- Improve route-level loading and empty-state consistency in the remaining viewer flows.
- Continue modernizing the remaining older pages so they use the same shell, feedback, and data-display patterns as the rest of the app.
- Continue targeted page-performance work on the heaviest remaining non-table UI bundles.

## Still To Do

### Frontend Architecture and UX

- Fix auth bootstrap and protected-route timing.
- Add global route/app loading UX.
- Consolidate toast/confirm patterns through PrimeVue services.
- Start feature-first frontend restructuring.
- Begin incremental TypeScript migration in stores, composables, and shared DTOs.
- Redesign the app shell and key pages.
- Continue modernizing older admin pages that still rely on bespoke layouts instead of shared page primitives.

### Performance

- Reduce oversized frontend chunks.
- Improve map request, rendering, and filtering performance.
- Add targeted code-splitting for heavy routes.
- Validate whether additional route-level lazy boundaries are still needed after manual chunk splitting.

### Backend Architecture

- Make transaction boundaries explicit.
- Extract oversized route modules into clearer services/repositories.
- Consolidate Redis access patterns.

### Testing and CI

- Expand frontend test coverage beyond the initial smoke test.
- Add backend regression tests for the new upload streaming and cache invalidation behavior.
- Revisit CI and deployment semantics after the next architecture pass.

## Notes

- The modernization is being implemented incrementally, with each slice ending in passing validation before moving on.
- Removing the last PrimeVue data-table consumers eliminated the old `prime-data` build chunk; the main remaining UI hotspot is now the broader `prime-ui` bundle.
- `@tailwindcss/vite` `4.2.1` is currently the latest available package, but it still declares peer support only through Vite 7. The app builds successfully on Vite 8, so this is currently a peer-metadata warning rather than a functional failure.