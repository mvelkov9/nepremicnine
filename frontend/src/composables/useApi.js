import axios from 'axios'
import { i18n } from '../i18n'
import { getApiErrorMessage } from '../utils/apiError'
import { useToast } from './useToast'

const api = axios.create({
  baseURL: '',
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
})

let refreshPromise = null
let loginRedirectScheduled = false

function clearStoredSession() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
}

function redirectToLogin() {
  if (loginRedirectScheduled) {
    return
  }

  loginRedirectScheduled = true
  window.location.assign('/login')
}

async function refreshAccessToken(refreshToken) {
  if (!refreshPromise) {
    refreshPromise = axios
      .post('/api/auth/refresh', {
        refresh_token: refreshToken,
      })
      .then(({ data }) => {
        localStorage.setItem('access_token', data.access_token)
        if (data.refresh_token) {
          localStorage.setItem('refresh_token', data.refresh_token)
        }
        return data.access_token
      })
      .catch((error) => {
        clearStoredSession()
        redirectToLogin()
        throw error
      })
      .finally(() => {
        refreshPromise = null
      })
  }

  return refreshPromise
}

// Request interceptor: attach JWT
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor: handle 401 refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config || {}
    const status = error.response?.status
    const isCanceled = error.code === 'ERR_CANCELED'
    const isRefreshRequest = String(original.url || '').includes('/api/auth/refresh')

    if (status === 401 && !original._retry && !original.skipAuthRefresh && !isRefreshRequest) {
      original._retry = true
      const refreshToken = localStorage.getItem('refresh_token')
      if (refreshToken) {
        try {
          const accessToken = await refreshAccessToken(refreshToken)
          original.headers = original.headers || {}
          original.headers.Authorization = `Bearer ${accessToken}`
          return api(original)
        } catch {
          return Promise.reject(error)
        }
      }

      clearStoredSession()
      redirectToLogin()
    }

    const skipErrorToast = original.skipErrorToast || original.meta?.skipErrorToast
    if (!skipErrorToast && !isCanceled && status !== 401) {
      const { showToast } = useToast()
      const message = getApiErrorMessage(error, i18n.global.t)
      showToast(message, 'error')
    }

    return Promise.reject(error)
  },
)

export default api
