# Phase 2: Frontend Core

**Status:** ✅ Complete  
**Commit:** `1def8db`

## Checklist

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

## Key Files

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
