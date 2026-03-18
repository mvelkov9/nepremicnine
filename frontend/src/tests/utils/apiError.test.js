import { describe, it, expect } from 'vitest'
import { getApiErrorMessage } from '@/utils/apiError'

// Minimal mock translator that returns the key
const t = (key, params) => {
  if (params) return `${key}:${JSON.stringify(params)}`
  return key
}

describe('getApiErrorMessage', () => {
  it('returns common.error for empty error', () => {
    expect(getApiErrorMessage({}, t)).toBe('common.error')
  })

  it('returns error.timeout for ECONNABORTED', () => {
    expect(getApiErrorMessage({ code: 'ECONNABORTED' }, t)).toBe('error.timeout')
  })

  it('returns error.unauthorized for 401', () => {
    expect(getApiErrorMessage({ response: { status: 401 } }, t)).toBe('error.unauthorized')
  })

  it('returns error.forbidden for 403', () => {
    expect(getApiErrorMessage({ response: { status: 403 } }, t)).toBe('error.forbidden')
  })

  it('returns error.notFound for 404', () => {
    expect(getApiErrorMessage({ response: { status: 404 } }, t)).toBe('error.notFound')
  })

  it('returns error.rateLimited for 429', () => {
    expect(getApiErrorMessage({ response: { status: 429 } }, t)).toBe('error.rateLimited')
  })

  it('returns error.server for 500+', () => {
    expect(getApiErrorMessage({ response: { status: 500 } }, t)).toBe('error.server')
    expect(getApiErrorMessage({ response: { status: 503 } }, t)).toBe('error.server')
  })

  it('translates known detail key', () => {
    const error = { response: { status: 401, data: { detail: 'Invalid credentials' } } }
    expect(getApiErrorMessage(error, t)).toBe('errorDetail.invalidCredentials')
  })

  it('passes unknown detail through unchanged', () => {
    const error = { response: { status: 400, data: { detail: 'Unknown business error' } } }
    expect(getApiErrorMessage(error, t)).toBe('Unknown business error')
  })

  it('returns error.message fallback when no response', () => {
    const error = { message: 'Network Error' }
    expect(getApiErrorMessage(error, t)).toBe('Network Error')
  })
})
