import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const api = {
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
}

vi.mock('../composables/useApi', () => ({
  default: api,
}))

describe('auth store', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    setActivePinia(createPinia())
  })

  it('marks itself initialized without a stored session', async () => {
    const { useAuthStore } = await import('./auth')
    const auth = useAuthStore()

    await auth.init()

    expect(auth.initialized).toBe(true)
    expect(api.get).not.toHaveBeenCalled()
  })

  it('deduplicates init requests and loads the current user once', async () => {
    localStorage.setItem('access_token', 'token')
    api.get.mockResolvedValue({
      data: {
        id: 1,
        full_name: 'Admin User',
        role: 'admin',
      },
    })

    const { useAuthStore } = await import('./auth')
    const auth = useAuthStore()

    await Promise.all([auth.init(), auth.init()])

    expect(api.get).toHaveBeenCalledTimes(1)
    expect(auth.initialized).toBe(true)
    expect(auth.isAdmin).toBe(true)
  })
})
