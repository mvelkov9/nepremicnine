import { test, expect } from '@playwright/test'
import nodePath from 'node:path'
import { hasTestCredentials, loginAsTestUser } from './helpers/auth'

const viewerRoutes = [
  '/',
  '/trg',
  '/regije',
  '/obcine',
  '/napoved',
  '/analiza',
  '/zemljevid',
  '/dokaz',
]

const adminRoutes = ['/admin', '/admin/uporabniki', '/admin/dokaz']

function screenshotName(routePath: string) {
  return routePath === '/' ? 'dashboard' : routePath.replace(/[\\/]/g, '-').replace(/^-+/, '')
}

test.describe('Authenticated smoke', () => {
  test.skip(!hasTestCredentials(), 'PLAYWRIGHT_TEST_EMAIL and PLAYWRIGHT_TEST_PASSWORD are required')

  test('viewer and admin routes render without console errors', async ({ page }) => {
    test.setTimeout(3 * 60 * 1000)

    const consoleErrors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text())
    })

    await loginAsTestUser(page)

    for (const routePath of [...viewerRoutes, ...adminRoutes]) {
      await test.step(`open ${routePath}`, async () => {
        await page.goto(routePath, { waitUntil: 'domcontentloaded' })
        await page.waitForLoadState('networkidle', { timeout: 20000 }).catch(() => {})
        await expect(page.locator('.app-boot-overlay')).not.toBeVisible({ timeout: 20000 })
        await expect(page.locator('#main-content')).toBeVisible({ timeout: 20000 })
        await expect(page.locator('#main-content h1, #main-content h2').first()).toBeVisible({
          timeout: 20000,
        })

        if (process.env.PLAYWRIGHT_CAPTURE_SMOKE === '1') {
          await page.screenshot({
            path: nodePath.resolve(
              'test-results',
              'smoke-captures',
              `${screenshotName(routePath)}.png`,
            ),
            fullPage: true,
          })
        }
      })
    }

    const unexpectedErrors = consoleErrors.filter(
      (entry) =>
        !entry.includes('Failed to load resource') &&
        !entry.includes('net::ERR_') &&
        !entry.includes('favicon'),
    )

    expect(unexpectedErrors).toEqual([])
  })
})
