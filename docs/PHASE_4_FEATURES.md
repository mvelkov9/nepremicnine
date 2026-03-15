# Phase 4: Features

**Status:** ✅ Complete  
**Commit:** `fc18742`

## Checklist

- [x] Map page: Leaflet with transaction markers + year/municipality/type filters
- [x] D96/TM → WGS84 coordinate conversion for Slovenian cadastral data
- [x] Diagnostics page: per-type and per-region model performance charts
- [x] Listing Analysis page: JSON/CSV listing input, scoring vs model, deviation charts
- [x] Admin panel: user management (list, update role, activate/deactivate, delete)
- [x] Complete i18n for all views and components (SI + EN)
- [x] Property type filter on dashboard stats

## Key Files

| File | Purpose |
|------|---------|
| `src/views/MapView.vue` | Leaflet map with transaction markers, popup details, filters |
| `src/views/DiagnosticsView.vue` | Per-type R²/MAE bar charts, per-region accuracy heatmap |
| `src/views/AnalysisView.vue` | Paste/upload listings → score against model → deviation chart |
| `src/views/AdminView.vue` | User table, role dropdown, activate/deactivate toggle, delete |
| `app/api/analysis.py` | `/api/analysis/score` — score listings against trained model |
| `app/api/admin.py` | Admin CRUD: list users, update role/status, delete |

## Frontend Routes (all views)

| Route | View | Auth | Description |
|-------|------|------|-------------|
| `/login` | LoginView | guest | Login + Register |
| `/` | DashboardView | auth | KPI cards + charts |
| `/podatki` | DataView | auth | Dataset management |
| `/model` | ModelView | auth | Model training + metrics |
| `/napoved` | PredictionView | auth | Price prediction form |
| `/zemljevid` | MapView | auth | Transaction map |
| `/diagnostika` | DiagnosticsView | auth | Model diagnostics |
| `/analiza` | AnalysisView | auth | Listing analysis |
| `/admin` | AdminView | admin | User management |
