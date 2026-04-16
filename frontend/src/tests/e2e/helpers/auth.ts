import { expect, type Page } from '@playwright/test'

export const testEmail = process.env.PLAYWRIGHT_TEST_EMAIL || ''
export const testPassword = process.env.PLAYWRIGHT_TEST_PASSWORD || ''

export function hasTestCredentials() {
  return Boolean(testEmail && testPassword)
}

export async function applyUserPreferences(
  page: Page,
  preferences: {
    theme: 'light' | 'dark'
    locale: 'sl' | 'en'
  },
) {
  await page.goto('/login')
  await page.evaluate(
    ({ theme, locale }) => {
      window.localStorage.setItem('theme', theme)
      window.localStorage.setItem('locale', locale)
      document.documentElement.setAttribute('data-theme', theme)
    },
    preferences,
  )
}

export async function loginAsTestUser(page: Page) {
  if (!hasTestCredentials()) {
    throw new Error('PLAYWRIGHT_TEST_EMAIL and PLAYWRIGHT_TEST_PASSWORD must be set')
  }

  const loginResponse = await page.request.post('/api/auth/login', {
    data: { email: testEmail, password: testPassword },
  })
  expect(loginResponse.ok()).toBeTruthy()
  const tokens = await loginResponse.json()

  const profileResponse = await page.request.get('/api/auth/me', {
    headers: {
      Authorization: `Bearer ${tokens.access_token}`,
    },
  })
  expect(profileResponse.ok()).toBeTruthy()
  const user = await profileResponse.json()

  await page.goto('/login')
  await page.evaluate(
    ([accessToken, refreshToken, authUser]) => {
      window.localStorage.setItem('access_token', accessToken)
      window.localStorage.setItem('refresh_token', refreshToken)
      window.localStorage.setItem('auth_user', JSON.stringify(authUser))
    },
    [tokens.access_token, tokens.refresh_token, user] as const,
  )
  await page.goto('/')
  await expect(page).toHaveURL(/\/$/)
  await expect(page.locator('#main-content')).toBeVisible()
}
