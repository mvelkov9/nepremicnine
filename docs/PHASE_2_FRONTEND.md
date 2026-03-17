# Phase 2: Frontend Core

**Status:** ✅ Complete  
**Commit:** `1def8db`

> Historical note: Phase 2 originally shipped as a Vue 3 + Vite SPA. The current `feat/nuxt-ui-redesign` branch has since moved the live frontend to Nuxt 3 + Nitro while preserving the same product routes and business flows.

## Current Frontend Architecture

- **Runtime**: Nuxt 3 application served by Nitro in both development and production
- **UI system**: `@nuxt/ui` + Tailwind 4, with a compatibility layer still wrapping some migrated legacy controls
- **Routing**: file-based Nuxt pages preserve `/login`, `/`, `/napoved`, `/zemljevid`, `/analiza`, `/obcine/:slug`, and `/admin*`
- **Auth**: SSR-aware bootstrap with HttpOnly access/refresh cookies as the browser default, while bearer-token support remains available during migration
- **API access**: browser `/api/*` requests stay same-origin through `frontend/server/routes/api/[...path].ts`, which proxies to FastAPI
- **State and i18n**: Pinia remains the state layer and existing Slovenian/English locale content is loaded through a Nuxt plugin

## Current Key Files

| File | Purpose |
|------|---------|
| `frontend/app.vue` | Root Nuxt app shell bootstrap |
| `frontend/layouts/default.vue` | Main authenticated application chrome |
| `frontend/layouts/auth.vue` | Login/authentication layout |
| `frontend/pages/` | File-based viewer and admin routes |
| `frontend/middleware/` | Guest/auth/admin route protection |
| `frontend/server/routes/api/[...path].ts` | Same-origin Nitro proxy to the FastAPI backend |
| `frontend/plugins/i18n.js` | `vue-i18n` plugin registration for Nuxt |
| `frontend/legacy/views/` | Migrated page implementations still being moved into fully Nuxt-native structure |
| `frontend/components/primevue/` | Compatibility shims used by remaining migrated legacy views |
| `frontend/assets/css/app.css` | Shared surface, typography, and interaction styling for the redesigned UI |

## Historical Delivery Checklist

- [x] Pinia stores: useAuthStore, useDataStore, useModelStore, useStatsStore
- [x] Login/Register pages with JWT authentication
- [x] Dashboard: KPI cards + Chart.js bar/doughnut charts
- [x] Data Management: drag-and-drop upload, table with preview, delete
- [x] Data Preparation: ETN pair detection, bulk prepare
- [x] AppLayout component (collapsible sidebar + top nav + locale switcher)
- [x] useApi composable (axios + JWT auto-refresh interceptor)
- [x] Vue Router with 9 routes + auth guards (guest/auth/admin)
- [x] Responsive layout
- [x] i18n: full Slovenian + English translations

## Historical Key Files

| File | Purpose |
|------|---------|
| `src/views/LoginView.vue` | Login + Register forms with tab switching |
| `src/views/DashboardView.vue` | KPI cards, bar chart (top regions), doughnut (type distribution) |
| `src/views/DataView.vue` | CSV upload, dataset table, row preview, delete |
| `src/stores/auth.js` | JWT auth state (login, register, refresh, logout) |
| `src/stores/data.js` | Datasets CRUD + upload progress |
| `src/stores/model.js` | Model info, training status, feature importance |
| `src/stores/stats.js` | Dashboard statistics (overview, regions, distribution, trend) |
| `src/composables/useApi.js` | Axios instance with JWT headers + 401 auto-refresh |
| `src/components/AppLayout.vue` | Sidebar nav + top bar + i18n locale switcher |
| `src/router/index.js` | Route definitions + navigation guards |
| `src/locales/sl.json` | Slovenian translations |
| `src/locales/en.json` | English translations |

## Store Architecture

```
useAuthStore         useDataStore         useStatsStore        useModelStore
├── user             ├── datasets         ├── overview         ├── info
├── token            ├── upload()         ├── regions          ├── importance
├── login()          ├── fetch()          ├── distribution     ├── training
├── register()       ├── delete()         ├── trend            ├── startTraining()
├── refresh()        └── preview()        └── fetchAll()       └── fetchInfo()
└── logout()
```
