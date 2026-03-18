interface User {
  id: number
  email: string
  full_name: string
  avatar_url: string | null
  role: 'admin' | 'viewer'
  is_active: boolean
  created_at: string
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const initialized = ref(false)

  const isAuthenticated = computed(() => !!user.value)
  const isAdmin = computed(() => user.value?.role === 'admin')

  const api = useApi()

  async function login(email: string, password: string): Promise<void> {
    await api.post('/api/auth/login', { email, password })
    await fetchUser()
  }

  async function fetchUser(): Promise<User | null> {
    try {
      const { data } = await api.get<User>('/api/auth/me')
      user.value = data ?? null
      return user.value
    } catch {
      clearState()
      return null
    }
  }

  async function logout(): Promise<void> {
    try {
      await api.post('/api/auth/logout', {})
    } catch {
      // Ignore errors — clear local state regardless
    }
    clearState()
  }

  async function init(): Promise<User | null> {
    if (initialized.value) return user.value
    initialized.value = true
    return fetchUser()
  }

  async function updateProfile(
    payload: Partial<Pick<User, 'full_name' | 'avatar_url'>>,
  ): Promise<User | null> {
    const { data } = await api.patch<User>('/api/auth/me', payload)
    user.value = data ?? null
    return user.value
  }

  function clearState(): void {
    user.value = null
  }

  return {
    user,
    initialized,
    isAuthenticated,
    isAdmin,
    login,
    logout,
    fetchUser,
    init,
    updateProfile,
    clearState,
  }
})
