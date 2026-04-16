import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { useLocalStorage } from '@vueuse/core'
import api from '../composables/useApi'
import { accessToken, refreshToken } from './tokens'
import type { User } from '../types/api'

export { accessToken, refreshToken }

export const useAuthStore = defineStore('auth', () => {
  const user = useLocalStorage<User | null>('auth_user', null, {
    serializer: {
      read: (v: string) => (v ? JSON.parse(v) : null),
      write: (v: User | null) => JSON.stringify(v),
    },
  })

  const bootstrapStatus = ref<'idle' | 'loading' | 'ready'>('idle')
  let initPromise: Promise<void> | null = null

  const hasToken = computed(() => !!accessToken.value)
  const isAuthenticated = computed(() => !!accessToken.value && !!user.value)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const isBootstrapping = computed(() => bootstrapStatus.value === 'loading')
  const isReady = computed(() => bootstrapStatus.value === 'ready')

  function clearAuthState() {
    user.value = null
    accessToken.value = null
    refreshToken.value = null
  }

  async function login(email: string, password: string): Promise<void> {
    const { data } = await api.post('/api/auth/login', { email, password })
    accessToken.value = data.access_token
    if (data.refresh_token) {
      refreshToken.value = data.refresh_token
    }
    bootstrapStatus.value = 'loading'
    await fetchUser()
  }

  async function fetchUser(): Promise<void> {
    try {
      const { data } = await api.get<User>('/api/auth/me')
      user.value = data
    } catch {
      clearAuthState()
    } finally {
      bootstrapStatus.value = 'ready'
    }
  }

  async function logout(): Promise<void> {
    try {
      await api.post('/api/auth/logout', { refresh_token: refreshToken.value })
    } catch {
      // Ignore errors and clear local state regardless.
    }
    clearAuthState()
    bootstrapStatus.value = 'ready'
  }

  async function init(): Promise<void> {
    if (initPromise) return initPromise

    bootstrapStatus.value = 'loading'
    initPromise = (async () => {
      if (accessToken.value) {
        await fetchUser()
      } else {
        bootstrapStatus.value = 'ready'
      }
    })()

    try {
      await initPromise
    } finally {
      initPromise = null
    }
  }

  async function updateProfile(
    payload: Partial<Pick<User, 'full_name' | 'avatar_url'>>,
  ): Promise<User> {
    const { data } = await api.patch<User>('/api/auth/me', payload)
    user.value = data
    return data
  }

  return {
    user,
    accessToken,
    hasToken,
    bootstrapStatus,
    isBootstrapping,
    isReady,
    isAuthenticated,
    isAdmin,
    login,
    logout,
    fetchUser,
    init,
    updateProfile,
  }
})
