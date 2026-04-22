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

const emptyExplorer = {
  items: [],
  total: 0,
  page: 1,
  page_size: 12,
  pages: 0,
  filters: {},
  sort: 'recent',
  order: 'desc',
}

test.describe('Authenticated shell layout', () => {
  test('keeps the workspace header compact and leaves the page hero as the main heading', async ({
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
          return json({ unread: 2 })
        case '/api/workspaces':
          return json([])
        case '/api/watchlists/feed':
          return json([])
        case '/api/regions/municipalities':
          return json([{ municipality: 'Ljubljana', region: 'Osrednjeslovenska' }])
        case '/api/stats/market-home':
          return json({
            headline: {
              total_records: 120,
              earliest_year: 2020,
              latest_year: 2025,
              median_price: 250000,
              avg_price_per_m2: 3200,
            },
            market_coverage: {
              present: 1,
              official_total: 212,
            },
            property_type_mix: [{ property_type: 'stanovanje', count: 80, share: 0.67 }],
            year_coverage: [{ year: 2025, count: 20 }],
          })
        case '/api/stats/trend':
          return json([
            { year: 2024, count: 10, median_price: 200000, avg_price_per_m2: 3000 },
            { year: 2025, count: 12, median_price: 230000, avg_price_per_m2: 3200 },
          ])
        case '/api/stats/transactions':
        case '/api/stats/regions-explorer':
        case '/api/stats/municipalities':
          return json(emptyExplorer)
        default:
          return json({})
      }
    })

    await page.addInitScript((user) => {
      window.localStorage.setItem('access_token', 'demo-token')
      window.localStorage.setItem('refresh_token', 'demo-refresh')
      window.localStorage.setItem('auth_user', JSON.stringify(user))
    }, mockUser)

    await page.goto('/')
    await expect(page.locator('#main-content')).toBeVisible()
    await expect(page.locator('.shell-topbar h1')).toHaveCount(0)
    await expect(page.locator('.shell-topbar .page-heading')).toContainText(
      /Dashboard|Nadzorna plošča/,
    )
    await expect(page.locator('.shell-topbar .page-description')).toHaveCount(0)
    await expect(page.locator('.shell-utility-cluster')).toBeVisible()
    await expect(page.locator('#main-content h1')).toHaveCount(1)
  })
})
