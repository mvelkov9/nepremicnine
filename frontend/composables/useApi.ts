import { $fetch, type FetchError } from 'ofetch'

let refreshPromise: Promise<void> | null = null

interface ApiConfig {
  params?: Record<string, unknown>
  headers?: Record<string, string>
  timeout?: number
}

interface NormalizedError extends Error {
  code?: string
  response: {
    status: number
    data: unknown
  }
}

type RawFetchError = FetchError & {
  response?: {
    status?: number
    data?: unknown
    _data?: unknown
  }
  data?: unknown
  statusCode?: number
}

interface RequestOptions {
  method?: string
  body?: BodyInit | Record<string, any> | null
  query?: Record<string, unknown>
  headers?: HeadersInit | Record<string, string>
  credentials?: RequestCredentials
}

type RequestFetch = <T>(url: string, options?: RequestOptions) => Promise<T>

function normalizePayload(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(normalizePayload)
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([k, v]) => [k, normalizePayload(v)]),
    )
  }
  return value
}

function normalizeApiError(error: unknown): NormalizedError {
  const raw = error as RawFetchError
  const normalizedData = normalizePayload(
    raw.data ??
      raw.response?.data ??
      raw.response?._data ?? { detail: raw.message || 'Unknown API error' },
  )

  const wrapped = new Error(
    (raw.data as Record<string, string>)?.detail || raw.message || 'API request failed',
  ) as NormalizedError
  wrapped.code = raw.name === 'AbortError' ? 'ECONNABORTED' : raw.name
  wrapped.response = {
    status: raw.response?.status || raw.statusCode || 500,
    data: normalizedData,
  }
  return wrapped
}

function getRequestFetch(): RequestFetch {
  if (import.meta.server) {
    const requestFetch = useRequestFetch()
    return ((url, options) => requestFetch(url, options as any)) as RequestFetch
  }
  return ((url, options) => $fetch(url, options as any)) as RequestFetch
}

async function refreshAuthCookie(): Promise<void> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const requestFetch = getRequestFetch()
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

async function request<T = unknown>(
  method: string,
  url: string,
  payload?: unknown,
  config: ApiConfig = {},
  retried = false,
): Promise<{ data: T }> {
  const requestFetch = getRequestFetch()

  const headers: Record<string, string> = { ...(config.headers || {}) }
  const requestBody = payload as BodyInit | Record<string, any> | null | undefined
  if (payload instanceof FormData) {
    delete headers['Content-Type']
  }

  try {
    const data = await requestFetch<T>(url, {
      method,
      body: requestBody,
      query: config.params,
      headers,
      credentials: 'include',
    })
    return { data: normalizePayload(data) as T }
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
        return request<T>(method, url, payload, config, true)
      } catch {
        if (import.meta.client && window.location.pathname !== '/login') {
          window.location.href = '/login'
        }
      }
    }

    throw error
  }
}

const useApi = () => ({
  get<T = unknown>(url: string, config?: ApiConfig) {
    return request<T>('GET', url, undefined, config)
  },
  post<T = unknown>(url: string, payload?: unknown, config?: ApiConfig) {
    return request<T>('POST', url, payload, config)
  },
  patch<T = unknown>(url: string, payload?: unknown, config?: ApiConfig) {
    return request<T>('PATCH', url, payload, config)
  },
  put<T = unknown>(url: string, payload?: unknown, config?: ApiConfig) {
    return request<T>('PUT', url, payload, config)
  },
  delete<T = unknown>(url: string, config?: ApiConfig) {
    return request<T>('DELETE', url, undefined, config)
  },
})

export default useApi
export type { ApiConfig }
