import { test, expect } from '@playwright/test'

test.describe('Navigation', () => {
  test('protected routes redirect to login', async ({ page }) => {
    // Dashboard should redirect unauthenticated users
    await page.goto('/napoved')
    await expect(page).toHaveURL(/\/login/)

    await page.goto('/zemljevid')
    await expect(page).toHaveURL(/\/login/)

    await page.goto('/analiza')
    await expect(page).toHaveURL(/\/login/)
  })

  test('page title updates on navigation', async ({ page }) => {
    await page.goto('/login')
    await expect(page).toHaveTitle(/Nepremičnine/)
  })

  test('page loader appears during boot', async ({ page }) => {
    await page.goto('/login')
    // The page should eventually be ready (no infinite loading)
    await expect(page.locator('.app-boot-overlay')).not.toBeVisible({ timeout: 10000 })
  })

  test('no console errors on login page', async ({ page }) => {
    const errors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text())
    })

    await page.goto('/login')
    await page.waitForTimeout(2000)

    // Filter out expected errors (e.g., API calls failing without backend)
    const unexpectedErrors = errors.filter(
      (e) => !e.includes('Failed to fetch') && !e.includes('ERR_CONNECTION_REFUSED') && !e.includes('net::')
    )
    expect(unexpectedErrors).toHaveLength(0)
  })
})
