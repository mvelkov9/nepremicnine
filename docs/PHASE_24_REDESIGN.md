# Phase 24 — Full Frontend Redesign (v0.13.0)

> Complete PrimeVue component migration, layout decomposition, dark/light mode consistency, and CSS cleanup.

| Item | Value |
|------|-------|
| **From Version** | 0.12.0 |
| **To Version** | 0.13.0 |
| **Scope** | All 12 views, AppLayout, global CSS, composables, constants |
| **Method** | Parallel agent-driven implementation with phased rollout |

---

## Summary

Migrated the entire frontend from a mix of raw HTML elements and PrimeVue components to a consistent, fully PrimeVue-based design system. Fixed dark mode issues, decomposed the monolithic AppLayout, and removed ~450 lines of deprecated CSS.

---

## Changes by Category

### Infrastructure (Phase 0)

- **PrimeVue services**: Registered `ConfirmationService` and `ToastService` in `main.ts`
- **JS to TS**: Converted `useApi.js` → `useApi.ts` and `navigation.js` → `navigation.ts` with proper types
- **TypeScript**: Added `lang="ts"` to all 12 view `<script setup>` blocks
- **Toast bridge**: Created bridge pattern (`useToast.ts`) for module-level toast calls outside Vue component context, with `App.vue` watcher draining pending items into PrimeVue Toast

### Shared Layer (Phase 1)

- **Toast**: Replaced custom `ToastContainer.vue` with PrimeVue `<Toast />` + bridge watcher in `App.vue`
- **Confirm**: Added PrimeVue `<ConfirmDialog />` globally, replaced browser `confirm()` in DataView and AdminView
- **CSS fixes**: Fixed duplicated `.p-button` rule, badge dark mode colors, `.feature-bar` background

### View Redesigns (Phase 2)

| View | Changes |
|------|---------|
| **AdminView** | Raw `<table>` → DataTable, `<button>` → Button, `<span class="badge">` → Tag, `confirm()` → useConfirm |
| **DiagnosticsView** | 4 raw tables → DataTable, `<select>` → Select, focus-chips → SelectButton, kpi-cards → MetricCard |
| **PrepareView** | Custom tabs → PrimeVue Tabs, `<textarea>` → Textarea, 3 tables → DataTable, badges → Tag |
| **LoginView** | `<input>` → InputText/Password, segmented-control → SelectButton, auth-switch → SelectButton, error `<p>` → Message |
| **MunicipalityView** | Raw `<table>` → DataTable, hero buttons → PrimeVue Button with icons |
| **DataView** | `<input type="file">` → FileUpload, `confirm()` → useConfirm, search → IconField + InputIcon |
| **DashboardView** | `.p-input-icon-left` → IconField + InputIcon |
| **PredictionView** | 5 raw buttons → PrimeVue Button, hardcoded colors → CSS variables |
| **MapView** | Legend chips → PrimeVue Button, rail cards → Button, hardcoded colors → CSS variables |

### Layout Decomposition (Phase 3)

- **AppLayout.vue**: Reduced from ~1150 lines to ~750 lines
- **New**: `components/layout/AppSidebar.vue` — sidebar navigation, brand, context card, workspace switch
- **New**: `components/layout/ProfileDialog.vue` — profile editing with avatar preview

### CSS Cleanup (Phase 4)

Removed ~450 lines of deprecated CSS from `main.css`:
- Old sidebar/topbar/nav styles (now scoped in AppSidebar/AppLayout)
- `.segmented-control`, `.segmented-btn` (replaced by PrimeVue SelectButton)
- `.ghost-btn`, `.danger-soft`, `.btn`, `.btn-primary`, `.icon-btn` (replaced by PrimeVue Button)
- `.profile-pill`, `.avatar-frame`, `.profile-copy` (now scoped in AppLayout)
- `.badge-*` classes (replaced by PrimeVue Tag)
- Raw `table`, `th`, `td` styles (replaced by PrimeVue DataTable)
- Raw `input`, `textarea`, `select` styles (replaced by PrimeVue form components)
- `.modal-overlay`, `.modal-content` (replaced by PrimeVue Dialog)
- `.progress-bar` (replaced by PrimeVue ProgressBar)
- `.auth-switch`, `.inline-link` (replaced by PrimeVue components)
- Cleaned responsive media queries of dead class references

### Visual Overhaul (Phase 5)

- **Sidebar grouping**: Added `group` field to `NavItem` interface, grouped viewer nav (Overview / Tools / Insights) and admin nav (Overview / Pipeline / Monitor) with section labels and dividers
- **AdminView**: Added global search filter, pagination, sortable columns, user count display
- **ModelView**: Sortable columns, R² severity Tags, theme-aware Chart.js colors via `getComputedStyle()`, icons on all buttons, replaced `model-source-pill` with PrimeVue Tag
- **DashboardView**: Added Analysis quick-action button, region column in largest markets table
- **MunicipalityView**: Year trend data as DataTable, improved color consistency, icons on all buttons
- **PrepareView**: Enhanced result display with detected pairs DataTable, icons on all action buttons
- **DiagnosticsView**: Fixed last hardcoded gradient color (`#7dd3fc` → `color-mix()`)

### Dark Mode Fixes

- Replaced hardcoded colors in PredictionView (`.estimate-card`, `.submit-btn`, `.context-card`) with CSS variables
- Replaced hardcoded colors in MapView (`.legend-chip.active`, `.flag-chip.active`) with `color-mix()` using CSS variables
- Fixed `.feature-bar` in DiagnosticsView: `rgb(15 23 42 / 8%)` → `var(--surface-muted)`
- Fixed `.active-focus-row`: hardcoded blue → `color-mix(in srgb, var(--primary) 8%, transparent)`
- Fixed `.feature-bar span` gradient: hardcoded `#7dd3fc` → `color-mix(in srgb, var(--primary) 40%, white)`

---

## Files Changed

### New Files
- `frontend/src/components/layout/AppSidebar.vue`
- `frontend/src/components/layout/ProfileDialog.vue`
- `frontend/src/composables/useAppToast.ts`
- `frontend/src/constants/navigation.ts` (renamed from .js)
- `frontend/src/composables/useApi.ts` (renamed from .js)

### Deleted Files
- `frontend/src/components/ToastContainer.vue`
- `frontend/src/composables/useApi.js`
- `frontend/src/constants/navigation.js`

### Modified Files
- `frontend/src/main.ts` — PrimeVue services
- `frontend/src/App.vue` — Toast bridge, ConfirmDialog
- `frontend/src/components/AppLayout.vue` — decomposed, typed
- `frontend/src/composables/useToast.ts` — bridge pattern rewrite
- `frontend/src/styles/main.css` — removed ~450 lines of deprecated CSS
- All 12 views — PrimeVue migration + TypeScript

---

## Verification

- Build: `pnpm build` passes with no errors
- Lint: `pnpm lint` passes with 0 errors, 0 warnings
- Type check: `vue-tsc --noEmit` — pre-existing view type warnings only (no new errors)
