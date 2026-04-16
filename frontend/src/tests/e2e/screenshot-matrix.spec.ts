import { test, expect } from '@playwright/test'
import nodePath from 'node:path'
import { applyUserPreferences, hasTestCredentials, loginAsTestUser } from './helpers/auth'

const routes = [
  '/',
  '/trg',
  '/regije',
  '/obcine',
  '/obcine/ljubljana',
  '/napoved',
  '/analiza',
  '/zemljevid',
  '/dokaz',
  '/admin',
  '/admin/podatki',
  '/admin/priprava',
  '/admin/model',
  '/admin/diagnostika',
  '/admin/uporabniki',
  '/admin/dokaz',
]

const variants = [
  { name: 'desktop-sl-light', width: 1440, height: 1200, locale: 'sl', theme: 'light' },
  { name: 'desktop-sl-dark', width: 1440, height: 1200, locale: 'sl', theme: 'dark' },
  { name: 'desktop-en-light', width: 1440, height: 1200, locale: 'en', theme: 'light' },
  { name: 'desktop-en-dark', width: 1440, height: 1200, locale: 'en', theme: 'dark' },
  { name: 'tablet-sl-light', width: 1024, height: 1366, locale: 'sl', theme: 'light' },
  { name: 'tablet-sl-dark', width: 1024, height: 1366, locale: 'sl', theme: 'dark' },
  { name: 'tablet-en-light', width: 1024, height: 1366, locale: 'en', theme: 'light' },
  { name: 'tablet-en-dark', width: 1024, height: 1366, locale: 'en', theme: 'dark' },
  { name: 'mobile-sl-light', width: 430, height: 932, locale: 'sl', theme: 'light' },
  { name: 'mobile-sl-dark', width: 430, height: 932, locale: 'sl', theme: 'dark' },
  { name: 'mobile-en-light', width: 430, height: 932, locale: 'en', theme: 'light' },
  { name: 'mobile-en-dark', width: 430, height: 932, locale: 'en', theme: 'dark' },
] as const

const routeFilterTokens = String(process.env.PLAYWRIGHT_ROUTE_FILTER || '')
  .split(',')
  .map((token) => token.trim())
  .filter(Boolean)
const variantFilterTokens = String(process.env.PLAYWRIGHT_VARIANT_FILTER || '')
  .split(',')
  .map((token) => token.trim())
  .filter(Boolean)
const activeRoutes = routeFilterTokens.length
  ? routes.filter((routePath) =>
      routeFilterTokens.some((token) => routePath.toLowerCase().includes(token.toLowerCase())),
    )
  : routes
const activeVariants = variantFilterTokens.length
  ? variants.filter((variant) =>
      variantFilterTokens.some((token) => variant.name.toLowerCase().includes(token.toLowerCase())),
    )
  : variants

function screenshotName(routePath: string) {
  return routePath === '/' ? 'dashboard' : routePath.replace(/[\\/]/g, '-').replace(/^-+/, '')
}

test.describe('Screenshot matrix', () => {
  test.skip(
    !hasTestCredentials() || process.env.PLAYWRIGHT_CAPTURE_MATRIX !== '1',
    'Matrix capture requires credentials and PLAYWRIGHT_CAPTURE_MATRIX=1',
  )

  test('capture authenticated routes across locales, themes, and breakpoints', async ({ page }) => {
    test.setTimeout(20 * 60 * 1000)

    await loginAsTestUser(page)

    for (const variant of activeVariants) {
      await test.step(`variant ${variant.name}`, async () => {
        await page.setViewportSize({ width: variant.width, height: variant.height })
        await applyUserPreferences(page, {
          locale: variant.locale,
          theme: variant.theme,
        })

        for (const routePath of activeRoutes) {
          await test.step(`${variant.name} ${routePath}`, async () => {
            const routeTimeout =
              routePath.includes('/admin/model') || routePath.includes('/admin/diagnostika')
                ? 60000
                : 25000
            await page.goto(routePath, { waitUntil: 'domcontentloaded' })
            await page.waitForLoadState('networkidle', { timeout: routeTimeout }).catch(() => {})
            await expect(page.locator('#main-content')).toBeVisible({ timeout: routeTimeout })
            await expect(page.locator('#main-content h1, #main-content h2').first()).toBeVisible({
              timeout: routeTimeout,
            })

            await page.screenshot({
              path: nodePath.resolve(
                'test-results',
                'route-matrix',
                variant.name,
                `${screenshotName(routePath)}.png`,
              ),
              fullPage: true,
            })
          })
        }
      })
    }
  })
})
