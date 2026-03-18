import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'

// Mock the API module
vi.mock('@/composables/useApi', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
    patch: vi.fn(),
  },
}))

// Mock the router
vi.mock('@/router', () => ({
  default: { push: vi.fn() },
}))

describe('auth store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('isAuthenticated is false when no token', () => {
    const auth = useAuthStore()
    auth.accessToken = null
    expect(auth.isAuthenticated).toBe(false)
  })

  it('isAdmin is false when user has viewer role', () => {
    const auth = useAuthStore()
    auth.user = { role: 'viewer' }
    expect(auth.isAdmin).toBe(false)
  })

  it('isAdmin is true when user has admin role', () => {
    const auth = useAuthStore()
    auth.user = { role: 'admin' }
    expect(auth.isAdmin).toBe(true)
  })

  it('isAdmin is false when user is null', () => {
    const auth = useAuthStore()
    auth.user = null
    expect(auth.isAdmin).toBe(false)
  })

  it('login stores access token and calls fetchUser', async () => {
    const api = (await import('@/composables/useApi')).default
    api.post.mockResolvedValueOnce({
      data: { access_token: 'test-token', refresh_token: 'refresh-token' },
    })
    api.get.mockResolvedValueOnce({
      data: { id: 1, email: 'test@example.com', role: 'viewer' },
    })

    const auth = useAuthStore()
    await auth.login('test@example.com', 'password')

    expect(auth.accessToken).toBe('test-token')
    expect(auth.user).toEqual({ id: 1, email: 'test@example.com', role: 'viewer' })
  })

  it('logout clears user and tokens', async () => {
    const api = (await import('@/composables/useApi')).default
    api.post.mockResolvedValueOnce({})

    const auth = useAuthStore()
    auth.user = { id: 1, role: 'admin' }
    auth.accessToken = 'some-token'

    await auth.logout()

    expect(auth.user).toBeNull()
    expect(auth.accessToken).toBeNull()
  })
})
