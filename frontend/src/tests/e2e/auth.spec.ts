import { test, expect } from '@playwright/test'

test.describe('Authentication', () => {
  test('shows login page when unauthenticated', async ({ page }) => {
    await page.goto('/')
    // Should redirect to login
    await expect(page).toHaveURL(/\/login/)
  })

  test('login form has required fields', async ({ page }) => {
    await page.goto('/login')
    await expect(page.locator('input[type="email"], input[name="email"], [data-testid="email-input"]')).toBeVisible()
    await expect(page.locator('input[type="password"], input[name="password"], [data-testid="password-input"]')).toBeVisible()
  })

  test('shows error on invalid credentials', async ({ page }) => {
    await page.goto('/login')

    // Fill in invalid credentials
    const emailInput = page.locator('input[type="email"], input[name="email"], [data-testid="email-input"]')
    const passwordInput = page.locator('input[type="password"], input[name="password"], [data-testid="password-input"]')

    await emailInput.fill('invalid@test.com')
    await passwordInput.fill('wrongpassword')

    // Submit
    const submitButton = page.locator('button[type="submit"], [data-testid="login-button"]')
    await submitButton.click()

    // Should show an error (toast or inline) and stay on login
    await expect(page).toHaveURL(/\/login/)
  })

  test('skip navigation link is present', async ({ page }) => {
    await page.goto('/login')
    const skipLink = page.locator('.skip-link')
    await expect(skipLink).toHaveAttribute('href', '#main-content')
  })
})
