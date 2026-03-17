import { $fetch } from 'ofetch'
import { useRequestFetch } from '#app'
import { i18n } from '../i18n'
import { getApiErrorMessage } from '../utils/apiError'
import { useToast } from './useToast'

let refreshPromise = null

function normalizePayload(value) {
  if (Array.isArray(value)) {
    return value.map((item) => normalizePayload(item))
  }

  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value).map(([key, nestedValue]) => [key, normalizePayload(nestedValue)]),
    )
  }

  return value
}

function createRequestOptions(method, payload, config = {}) {
  const headers = { ...(config.headers || {}) }
  if (payload instanceof FormData) {
    delete headers['Content-Type']
  }

  return {
    method,
    body: payload,
    query: config.params,
    headers,
    timeout: config.timeout,
    credentials: 'include',
  }
}

function normalizeApiError(error) {
  if (error?.response) return error

  const wrapped = new Error(error?.data?.detail || error?.message || 'API request failed')
  wrapped.code = error?.name === 'AbortError' ? 'ECONNABORTED' : error?.code
  wrapped.response = {
    status: error?.status || error?.statusCode || 500,
    data: normalizePayload(error?.data || { detail: error?.message || 'Unknown API error' }),
  }
  return wrapped
}

async function refreshAuthCookie() {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const requestFetch = import.meta.server ? useRequestFetch() : $fetch
      await requestFetch('/api/auth/refresh', {
        method: 'POST',
        body: {},
        credentials: 'include',
      })
    })().finally(() => {
      refreshPromise = null
    })
  }

  return refreshPromise
}

async function request(method, url, payload, config = {}, retried = false) {
  const requestFetch = import.meta.server ? useRequestFetch() : $fetch

  try {
    const data = await requestFetch(url, createRequestOptions(method, payload, config))
    return { data: normalizePayload(data) }
  } catch (rawError) {
    const error = normalizeApiError(rawError)
    const status = error.response?.status
    const canRefresh =
      status === 401 &&
      !retried &&
      !url.endsWith('/auth/login') &&
      !url.endsWith('/auth/refresh') &&
      !url.endsWith('/auth/logout')

    if (canRefresh) {
      try {
        await refreshAuthCookie()
        return request(method, url, payload, config, true)
      } catch {
        if (import.meta.client && window.location.pathname !== '/login') {
          window.location.href = '/login'
        }
      }
    }

    if (import.meta.client && status && status !== 401) {
      const { showToast } = useToast()
      const message = getApiErrorMessage(error, i18n.global.t)
      showToast(message, 'error')
    }

    throw error
  }
}

const api = {
  get(url, config = {}) {
    return request('GET', url, undefined, config)
  },
  post(url, payload, config = {}) {
    return request('POST', url, payload, config)
  },
  patch(url, payload, config = {}) {
    return request('PATCH', url, payload, config)
  },
  put(url, payload, config = {}) {
    return request('PUT', url, payload, config)
  },
  delete(url, config = {}) {
    return request('DELETE', url, undefined, config)
  },
}

export default api
