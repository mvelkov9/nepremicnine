# Frontend Migration Map

> Current frontend state as of March 17, 2026. This file tracks which routes are already Nuxt UI native and which still pass through legacy PrimeVue-era views.

## Current Rule

- New UI work should land directly in Nuxt pages/components.
- Remaining PrimeVue compatibility aliases in `frontend/nuxt.config.js` are temporary only.
- Remove a PrimeVue shim only after every route that depends on it has been migrated.

## Route Inventory

| Route                | Status         | Current Source                                                                        | Notes                                                                             |
| -------------------- | -------------- | ------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| `/login`             | Nuxt UI native | `frontend/pages/login.vue`                                                            | Still uses legacy stores/composables for auth and i18n state.                     |
| `/`                  | Nuxt UI native | `frontend/pages/index.vue`                                                            | Rebuilt as a Nuxt page with VueUse-driven async state and no legacy view wrapper. |
| `/admin`             | Nuxt UI native | `frontend/pages/admin/index.vue`                                                      | Rebuilt as a Nuxt page with admin workbench overview cards.                       |
| `/napoved`           | Legacy wrapper | `frontend/pages/napoved.vue` -> `frontend/legacy/views/PredictionView.vue`            | High-value viewer flow; next migration target.                                    |
| `/zemljevid`         | Legacy wrapper | `frontend/pages/zemljevid.vue` -> `frontend/legacy/views/MapView.vue`                 | Depends on Leaflet and modal/detail patterns.                                     |
| `/analiza`           | Legacy wrapper | `frontend/pages/analiza.vue` -> `frontend/legacy/views/AnalysisView.vue`              | Still imports multiple PrimeVue form controls.                                    |
| `/obcine/[slug]`     | Legacy wrapper | `frontend/pages/obcine/[slug].vue` -> `frontend/legacy/views/MunicipalityView.vue`    | Should be migrated together with dashboard/map storytelling.                      |
| `/admin/podatki`     | Legacy wrapper | `frontend/pages/admin/podatki.vue` -> `frontend/legacy/views/DataView.vue`            | Good candidate after admin home because it owns data quality work.                |
| `/admin/priprava`    | Legacy wrapper | `frontend/pages/admin/priprava.vue` -> `frontend/legacy/views/PrepareView.vue`        | Depends on checklist/selection patterns.                                          |
| `/admin/model`       | Legacy wrapper | `frontend/pages/admin/model.vue` -> `frontend/legacy/views/ModelView.vue`             | Most complex admin route; keep last in admin batch.                               |
| `/admin/diagnostika` | Legacy wrapper | `frontend/pages/admin/diagnostika.vue` -> `frontend/legacy/views/DiagnosticsView.vue` | Shares model data contracts with `/admin/model`.                                  |
| `/admin/uporabniki`  | Legacy wrapper | `frontend/pages/admin/uporabniki.vue` -> `frontend/legacy/views/AdminView.vue`        | Smaller admin route; reasonable early migration target.                           |

## Shared Legacy Dependencies Still Active

- `frontend/nuxt.config.js` still aliases `primevue/*` imports to local compatibility components.
- `frontend/components/primevue/*` still exists for compatibility while legacy views are being replaced.
- `frontend/legacy/stores/*`, `frontend/legacy/composables/*`, and `frontend/legacy/utils/*` are still the active data/domain layer for migrated and unmigrated routes.
- `frontend/legacy/views/*` remains the main blocker for full SSR-first routing because many pages still render through `ClientOnly`.

## Migration Order

1. `/napoved`
2. `/admin/podatki`
3. `/admin/uporabniki`
4. `/zemljevid`
5. `/obcine/[slug]`
6. `/analiza`
7. `/admin/priprava`
8. `/admin/diagnostika`
9. `/admin/model`

## Exit Criteria Before Removing PrimeVue Shims

- No page in `frontend/pages/**` imports or wraps `frontend/legacy/views/*`.
- No file in active app code imports `primevue/*`.
- `frontend/components/primevue/*` can be deleted without breaking lint, typecheck, build, or Docker image build.
- Viewer and admin routes render without `ClientOnly` fallback unless a browser-only library truly requires it.
