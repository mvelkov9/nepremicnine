import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../composables/useApi'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const accessToken = ref(null)
  const initialized = ref(false)

  const isAuthenticated = computed(() => !!user.value)
  const isAdmin = computed(() => user.value?.role === 'admin')

  async function login(email, password) {
    const { data } = await api.post('/api/auth/login', { email, password })
    accessToken.value = data.access_token || null
    await fetchUser()
  }

  async function fetchUser() {
    try {
      const { data } = await api.get('/api/auth/me')
      user.value = data ? { ...data } : null
      accessToken.value = 'cookie'
      return user.value
    } catch {
      clearState()
      return null
    }
  }

  async function logout() {
    try {
      await api.post('/api/auth/logout', {})
    } catch {
      // Ignore errors — clear local state regardless
    }
    clearState()
  }

  async function init() {
    if (initialized.value) return user.value
    initialized.value = true
    return fetchUser()
  }

  async function updateProfile(payload) {
    const { data } = await api.patch('/api/auth/me', payload)
    user.value = data ? { ...data } : null
    return user.value
  }

  function clearState() {
    user.value = null
    accessToken.value = null
  }

  return {
    user,
    accessToken,
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
