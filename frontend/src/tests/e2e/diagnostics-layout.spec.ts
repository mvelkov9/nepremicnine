import { test, expect } from '@playwright/test'

const mockUser = {
  id: 1,
  email: 'demo@example.com',
  full_name: 'Demo Admin',
  avatar_url: null,
  role: 'admin',
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
} as const

const modelInfo = {
  version: 'demo-model-v1',
  trained_at: '2026-04-01T12:00:00Z',
  rows: 1200,
  duration_sec: 18.6,
  per_type_count: 2,
  global_metrics: {
    mae: 12000,
    rmse: 16400,
    r2: 0.71,
    mape: 9.4,
    median_ae: 9800,
    n_train: 900,
    n_test: 300,
  },
  per_type_metrics: {
    stanovanje: {
      mae: 11000,
      rmse: 15000,
      r2: 0.74,
      mape: 8.8,
      n_train: 420,
      n_test: 120,
    },
    hisa: {
      mae: 13500,
      rmse: 17200,
      r2: 0.68,
      mape: 10.1,
      n_train: 260,
      n_test: 90,
    },
  },
  per_region_metrics: {
    Osrednjeslovenska: {
      mae: 10800,
      rmse: 14600,
      r2: 0.75,
      mape: 8.5,
    },
  },
} as const

const modelDiagnostics = {
  combined_metrics: {
    mae: 11800,
    rmse: 16000,
    r2: 0.72,
    mape: 9.1,
    median_ae: 9600,
  },
  variant_benchmarks: {
    production_combined: {
      label: 'Production combined',
      enabled_sources: { rn: true, ev: true, emv: true },
      metrics: { mae: 12000, rmse: 16400, r2: 0.71, mape: 9.4 },
      delta_vs_full_global: { mae: 200, r2: -0.01 },
      removed_features: [],
    },
    deterministic: {
      label: 'Deterministic enrichment',
      enabled_sources: { rn: true, ev: true },
      metrics: { mae: 11700, rmse: 15900, r2: 0.73, mape: 9.0 },
      delta_vs_full_global: { mae: -100, r2: 0.01 },
      removed_features: ['emv_zone'],
    },
    etn_only: {
      label: 'ETN only',
      enabled_sources: {},
      metrics: { mae: 12800, rmse: 17000, r2: 0.65, mape: 10.4 },
      delta_vs_full_global: { mae: 1000, r2: -0.07 },
      removed_features: ['rn', 'ev', 'emv'],
    },
    full_global: {
      label: 'Full global',
      enabled_sources: { rn: true, ev: true, emv: true },
      metrics: { mae: 11600, rmse: 15800, r2: 0.72, mape: 8.9 },
      delta_vs_full_global: { mae: 0, r2: 0 },
      removed_features: [],
    },
  },
  variant_matrix: {
    production_bundle: {
      label: 'Production bundle',
      enabled_sources: { rn: true, ev: true, emv: true },
      global_metrics: { mae: 12000, r2: 0.71 },
      combined_metrics: { mae: 11800, r2: 0.72 },
      per_type_count: 2,
    },
    deterministic_bundle: {
      label: 'Deterministic bundle',
      enabled_sources: { rn: true, ev: true },
      global_metrics: { mae: 11700, r2: 0.7 },
      combined_metrics: { mae: 11550, r2: 0.74 },
      per_type_count: 2,
    },
  },
  ev_baseline_metrics: {
    benchmark_metrics: { mae: 14600, rmse: 18100, r2: 0.61 },
    model_metrics_on_coverage: { mae: 11900, rmse: 16000, r2: 0.72 },
    coverage_rows: 120,
    coverage_ratio: 0.4,
    coverage_by_source: { ev: 120, rn: 114 },
    delta_vs_model: { r2: 0.11 },
    per_type_metrics: {
      stanovanje: {
        n: 60,
        mae: 14000,
        rmse: 17000,
        r2: 0.63,
        model_mae: 11100,
        model_r2: 0.75,
      },
    },
  },
  segment_diagnostics: {
    property_type: [{ segment: 'stanovanje', n: 120, r2: 0.74, mae: 11000, rmse: 15000 }],
  },
} as const

test.describe('Diagnostics layout', () => {
  test('surfaces summary cards first and keeps detailed benchmark tables behind folds', async ({
    page,
  }) => {
    await page.route('**/api/**', async (route) => {
      const url = new URL(route.request().url())

      const json = (body: unknown) =>
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(body),
        })

      switch (url.pathname) {
        case '/api/health':
          return json({
            status: 'ok',
            version: 'test-build',
            database: 'ok',
            redis: 'ok',
            model: 'demo',
          })
        case '/api/auth/me':
          return json(mockUser)
        case '/api/activity/unread':
          return json({ unread: 1 })
        case '/api/workspaces':
        case '/api/watchlists/feed':
          return json([])
        case '/api/model/info':
          return json(modelInfo)
        case '/api/model/diagnostics':
          return json(modelDiagnostics)
        default:
          return json({})
      }
    })

    await page.addInitScript((user) => {
      window.localStorage.setItem('access_token', 'demo-token')
      window.localStorage.setItem('refresh_token', 'demo-refresh')
      window.localStorage.setItem('auth_user', JSON.stringify(user))
    }, mockUser)

    await page.goto(
      '/admin/diagnostika?diagnostics_tab=benchmarks&diagnostics_benchmark_tab=variants',
    )

    await expect(page.locator('#main-content')).toBeVisible()
    await expect(page.locator('.diagnostics-section-intro:visible .context-chip')).toHaveCount(3)
    await expect(page.locator('.diagnostics-card .metric-card').first()).toBeVisible()

    const folds = page.locator('details.diagnostics-fold')
    await expect(folds).toHaveCount(3)

    const firstFold = folds.first()
    await expect(firstFold.locator('table')).not.toBeVisible()
    await firstFold.locator('summary').click()
    await expect(firstFold.locator('table')).toBeVisible()
  })
})
