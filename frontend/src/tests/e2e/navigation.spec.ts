import { test, expect } from '@playwright/test'

test.describe('Navigation', () => {
  test('protected routes redirect to login', async ({ page }) => {
    await page.goto('/napoved')
    await expect(page).toHaveURL(/\/login/)

    await page.goto('/zemljevid')
    await expect(page).toHaveURL(/\/login/)

    await page.goto('/analiza')
    await expect(page).toHaveURL(/\/login/)
  })

  test('page title updates on navigation', async ({ page }) => {
    await page.goto('/login')
    await expect(page).toHaveTitle(/Nepremi(?:č|c)nine/)
  })

  test('page loader appears during boot', async ({ page }) => {
    await page.goto('/login')
    await expect(page.locator('.app-boot-overlay')).not.toBeVisible({ timeout: 10000 })
  })

  test('no console errors on login page', async ({ page }) => {
    const errors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text())
    })

    await page.goto('/login')
    await page.waitForTimeout(2000)

    const unexpectedErrors = errors.filter(
      (message) =>
        !message.includes('Failed to fetch') &&
        !message.includes('ERR_CONNECTION_REFUSED') &&
        !message.includes('net::'),
    )
    expect(unexpectedErrors).toHaveLength(0)
  })
})
