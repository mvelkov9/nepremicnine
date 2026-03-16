import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../composables/useApi'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const accessToken = ref(localStorage.getItem('access_token') || null)

  const isAuthenticated = computed(() => !!accessToken.value)
  const isAdmin = computed(() => user.value?.role === 'admin')

  async function login(email, password) {
    const { data } = await api.post('/api/auth/login', { email, password })
    accessToken.value = data.access_token
    localStorage.setItem('access_token', data.access_token)
    if (data.refresh_token) {
      localStorage.setItem('refresh_token', data.refresh_token)
    }
    await fetchUser()
  }

  async function fetchUser() {
    try {
      const { data } = await api.get('/api/auth/me')
      user.value = data
    } catch {
      logout()
    }
  }

  async function logout() {
    const refreshToken = localStorage.getItem('refresh_token')
    try {
      await api.post('/api/auth/logout', { refresh_token: refreshToken })
    } catch {
      // Ignore errors — clear local state regardless
    }
    user.value = null
    accessToken.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  }

  async function init() {
    if (accessToken.value) {
      await fetchUser()
    }
  }

  return { user, accessToken, isAuthenticated, isAdmin, login, logout, fetchUser, init }
})
