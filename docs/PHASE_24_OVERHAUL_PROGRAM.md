# Phase 24-31 — 2026 Overhaul Program

> Major modernization program for pipeline stability, Nuxt UI completion, and full-product UX rebuild.

| Item | Value |
|------|-------|
| **Start Point** | v0.11.0 |
| **Method** | Agency-guided phased delivery |
| **Primary Constraint** | Keep production usable while replacing legacy PrimeVue-era UI and stabilizing CI/CD |

## Agency Roles

- **DevOps Automator + Reality Checker** — pipeline stabilization, Docker/CI parity, deployment evidence
- **Frontend Developer + UX Architect** — Nuxt UI migration, shell redesign, VueUse adoption, responsive behavior
- **Technical Writer + Project Shepherd** — phased execution tracking, README/DEPLOYMENT/MASTER alignment

## Phase 24 — Pipeline & Version Governance

- Fix frontend Docker image build so Nuxt lifecycle scripts run only after the full source tree exists.
- Fix frontend typecheck compatibility and make the dependency graph explicit instead of relying on transitive packages.
- Audit framework/runtime versions against official upstream sources and record upgrade decisions.
- Deliverable: lint, typecheck, build, and Docker image build all pass from a clean checkout.

## Phase 25 — Frontend Foundation Reset

- Remove remaining PrimeVue compatibility aliases from `nuxt.config.js`.
- Replace legacy direct `vue-router` and migration-era wiring with Nuxt-native patterns.
- Move shared state, i18n, and request helpers into clear Nuxt-first structure.
- Deliverable: no route wrapper depends on `frontend/components/primevue`.

## Phase 26 — Design System & Shell

- Rebuild the app shell around Nuxt UI primitives and a tighter token system.
- Standardize cards, tables, filters, forms, toasts, empty states, loading states, and responsive breakpoints.
- Introduce VueUse where it materially reduces custom state or event plumbing.
- Deliverable: shell, auth, and shared patterns are consistent across viewer and admin surfaces.

## Phase 27 — Viewer Experience Rebuild

- Redesign dashboard, prediction, map, municipality, and analysis pages for denser market workflows.
- Replace custom/legacy widgets with Nuxt UI components and composables.
- Improve SEO/SSR metadata, page performance, and mobile interaction quality.
- Deliverable: viewer flows are fully Nuxt UI-based and no longer import legacy PrimeVue shims.

## Phase 28 — Admin Workbench Rebuild

- Rebuild data upload, preparation, model, diagnostics, and user-management screens with Nuxt UI.
- Improve long-running task visibility, empty/error handling, and operator ergonomics.
- Add safer bulk actions and better validation feedback.
- Deliverable: admin pages no longer rely on `frontend/legacy/views/*`.

## Phase 29 — Backend, Data, and Security Hardening

- Lock Python dependencies for reproducible builds and safer upgrades.
- Re-audit cache invalidation, async task reliability, API contracts, and rate/security headers.
- Expand regression tests around training, stats, auth cookies, and deployment-sensitive paths.
- Deliverable: backend installs are deterministic and critical routes have regression coverage.

## Phase 30 — Deployment & Runtime Simplification

- Decide explicitly between `build-on-VPS` and `pull-from-GHCR`; remove the half-and-half workflow.
- Align compose files, CI/CD, and runtime docs to the chosen deployment model.
- Add a concise VPS checklist covering reverse proxy, ports, secrets, backups, and verification.
- Deliverable: one deployment path, one set of docs, one validation checklist.

## Phase 31 — Documentation, Release, and Cleanup

- Update `README.md`, `docs/DEPLOYMENT.md`, and `docs/MASTER.md` to reflect the completed architecture.
- Remove dead migration artifacts, stale compatibility notes, and obsolete screenshots/instructions.
- Cut a release only after evidence-based verification of lint, typecheck, build, tests, and container startup.
- Deliverable: docs match the shipped system, not the migration history.

## Defaults Chosen

- Keep Nuxt 4 + Nitro as the frontend runtime.
- Keep Docker Compose as the deployment orchestrator for now.
- Treat CI/CD stabilization as phase 1 because the redesign cannot ship safely while builds are unreliable.
- Treat full PrimeVue removal as mandatory, but do it page-by-page to avoid breaking the app in one large cutover.
