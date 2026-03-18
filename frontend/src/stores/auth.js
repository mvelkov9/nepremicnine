import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useLocalStorage } from '@vueuse/core'
import api from '../composables/useApi'
import { useUiStore } from './ui'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const accessToken = useLocalStorage('access_token', null)
  const refreshToken = useLocalStorage('refresh_token', null)
  const initialized = ref(false)
  let initPromise = null

  const isAuthenticated = computed(() => !!accessToken.value)
  const isAdmin = computed(() => user.value?.role === 'admin')

  function clearSession() {
    user.value = null
    accessToken.value = null
    refreshToken.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  }

  async function login(email, password) {
    const { data } = await api.post('/api/auth/login', { email, password })
    accessToken.value = data.access_token
    if (data.refresh_token) {
      refreshToken.value = data.refresh_token
    }
    await fetchUser()
  }

  async function fetchUser() {
    try {
      const { data } = await api.get('/api/auth/me')
      user.value = data
    } catch {
      clearSession()
    }
  }

  async function logout() {
    try {
      await api.post('/api/auth/logout', { refresh_token: refreshToken.value })
    } catch {
      // Ignore errors — clear local state regardless
    }
    clearSession()
  }

  async function init() {
    if (initialized.value) {
      return
    }

    if (initPromise) {
      return initPromise
    }

    const ui = useUiStore()
    ui.beginBootstrapping()
    initPromise = (async () => {
      try {
        if (accessToken.value) {
          await fetchUser()
        }
      } finally {
        initialized.value = true
        ui.endBootstrapping()
        initPromise = null
      }
    })()

    return initPromise
  }

  async function updateProfile(payload) {
    const { data } = await api.patch('/api/auth/me', payload)
    user.value = data
    return data
  }

  return {
    user,
    accessToken,
    refreshToken,
    initialized,
    isAuthenticated,
    isAdmin,
    login,
    logout,
    fetchUser,
    init,
    updateProfile,
  }
})
