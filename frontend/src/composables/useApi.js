import axios from 'axios'
import { i18n } from '../i18n'
import { getApiErrorMessage } from '../utils/apiError'
import { useToast } from './useToast'
import router from '../router'
import { accessToken, refreshToken } from '../stores/tokens'

const api = axios.create({
  baseURL: '',
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
})

// Request interceptor: attach JWT
api.interceptors.request.use((config) => {
  if (accessToken.value) {
    config.headers.Authorization = `Bearer ${accessToken.value}`
  }
  return config
})

// Response interceptor: handle 401 refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true
      if (refreshToken.value) {
        try {
          const { data } = await axios.post('/api/auth/refresh', {
            refresh_token: refreshToken.value,
          })
          accessToken.value = data.access_token
          original.headers.Authorization = `Bearer ${data.access_token}`
          return api(original)
        } catch {
          accessToken.value = null
          refreshToken.value = null
          router.push({ name: 'login' })
        }
      }
    }
    // Show error toast for non-401 HTTP errors
    const status = error.response?.status
    if (status && status !== 401) {
      const { showToast } = useToast()
      const message = getApiErrorMessage(error, i18n.global.t)
      showToast(message, 'error')
    }
    return Promise.reject(error)
  },
)

export default api
