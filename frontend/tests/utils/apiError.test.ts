import { describe, it, expect } from 'vitest'
import { getApiErrorMessage } from '../../utils/apiError'

// Mock translation function.
// Returns the key for simple calls, and `key:{"param":value}` for calls with values,
// so we can assert on the exact i18n key (and interpolation params) that was used.
const t = (key: string, values?: Record<string, unknown>): string => {
  if (values) return `${key}:${JSON.stringify(values)}`
  return key
}

// Helper to build a minimal ApiError-shaped object
function makeError(opts: { status?: number; detail?: string; code?: string; message?: string }) {
  return {
    response: {
      status: opts.status,
      data: { detail: opts.detail },
    },
    code: opts.code,
    message: opts.message,
  }
}

describe('getApiErrorMessage — known detail strings', () => {
  const detailCases: [string, string][] = [
    ['No trained model found', 'errorDetail.noTrainedModel'],
    ['No trained model', 'errorDetail.noTrainedModel'],
    ['No trained model. Train first.', 'errorDetail.noTrainedModel'],
    ['CSV not found', 'errorDetail.csvNotFound'],
    ['Job not found', 'errorDetail.jobNotFound'],
    ['A training job is already queued or running', 'errorDetail.trainingAlreadyRunning'],
    ['Registration failed', 'errorDetail.registrationFailed'],
    ['Invalid credentials', 'errorDetail.invalidCredentials'],
    ['Account disabled', 'errorDetail.accountDisabled'],
    ['Invalid refresh token', 'errorDetail.invalidRefreshToken'],
    ['Refresh token has been revoked', 'errorDetail.invalidRefreshToken'],
    ['Cannot modify own account', 'errorDetail.cannotModifyOwnAccount'],
    ['Cannot delete own account', 'errorDetail.cannotDeleteOwnAccount'],
    ['Invalid role', 'errorDetail.invalidRole'],
    ['Path is outside the allowed data directory', 'errorDetail.invalidPath'],
    ['Symbolic links are not allowed', 'errorDetail.invalidPath'],
    ['Data preparation failed. Check server logs.', 'errorDetail.prepareFailed'],
    ['No profile changes submitted', 'errorDetail.noProfileChanges'],
    ['Full name is required', 'errorDetail.fullNameRequired'],
    ['Invalid avatar URL', 'errorDetail.invalidAvatarUrl'],
  ]

  it.each(detailCases)('detail "%s" maps to i18n key "%s"', (detail, expectedKey) => {
    const result = getApiErrorMessage(makeError({ detail }), t)
    expect(result).toBe(expectedKey)
  })
})

describe('getApiErrorMessage — "File exceeds" detail', () => {
  it('extracts the numeric limit from the detail string', () => {
    const result = getApiErrorMessage(makeError({ detail: 'File exceeds 10 MB limit' }), t)
    expect(result).toBe('errorDetail.fileTooLarge:{"limit":"10"}')
  })

  it('uses "?" when no number is present in the detail string', () => {
    const result = getApiErrorMessage(makeError({ detail: 'File exceeds the maximum size' }), t)
    expect(result).toBe('errorDetail.fileTooLarge:{"limit":"?"}')
  })
})

describe('getApiErrorMessage — unsupported file type detail', () => {
  it('maps "File type \'...\'" prefix to unsupportedFileType key', () => {
    const result = getApiErrorMessage(
      makeError({ detail: "File type 'application/exe' is not allowed" }),
      t,
    )
    expect(result).toBe('errorDetail.unsupportedFileType')
  })
})

describe('getApiErrorMessage — HTTP status codes (no detail)', () => {
  it('returns error.unauthorized for status 401', () => {
    expect(getApiErrorMessage(makeError({ status: 401 }), t)).toBe('error.unauthorized')
  })

  it('returns error.forbidden for status 403', () => {
    expect(getApiErrorMessage(makeError({ status: 403 }), t)).toBe('error.forbidden')
  })

  it('returns error.notFound for status 404', () => {
    expect(getApiErrorMessage(makeError({ status: 404 }), t)).toBe('error.notFound')
  })

  it('returns fileTooLarge with "?" limit for status 413', () => {
    expect(getApiErrorMessage(makeError({ status: 413 }), t)).toBe(
      'errorDetail.fileTooLarge:{"limit":"?"}',
    )
  })

  it('returns error.rateLimited for status 429', () => {
    expect(getApiErrorMessage(makeError({ status: 429 }), t)).toBe('error.rateLimited')
  })

  it('returns error.server for status 500', () => {
    expect(getApiErrorMessage(makeError({ status: 500 }), t)).toBe('error.server')
  })

  it('returns error.server for status 503', () => {
    expect(getApiErrorMessage(makeError({ status: 503 }), t)).toBe('error.server')
  })

  it('returns error.server for status 502', () => {
    expect(getApiErrorMessage(makeError({ status: 502 }), t)).toBe('error.server')
  })
})

describe('getApiErrorMessage — detail takes precedence over status', () => {
  it('uses detail translation even when a status code is also present', () => {
    const result = getApiErrorMessage(makeError({ status: 401, detail: 'Invalid credentials' }), t)
    // detail wins
    expect(result).toBe('errorDetail.invalidCredentials')
  })
})

describe('getApiErrorMessage — network / timeout errors', () => {
  it('returns error.timeout for ECONNABORTED code', () => {
    const result = getApiErrorMessage(makeError({ code: 'ECONNABORTED' }), t)
    expect(result).toBe('error.timeout')
  })
})

describe('getApiErrorMessage — unknown / fallback errors', () => {
  it('returns the error message string when status is unrecognised and no detail', () => {
    const result = getApiErrorMessage(makeError({ status: 418, message: 'I am a teapot' }), t)
    expect(result).toBe('I am a teapot')
  })

  it('falls back to common.error key when there is no useful information', () => {
    const result = getApiErrorMessage({}, t)
    expect(result).toBe('common.error')
  })

  it('falls back to common.error when error is empty object with no message', () => {
    const result = getApiErrorMessage({ message: '' }, t)
    // empty string is falsy, so falls through to t('common.error')
    expect(result).toBe('common.error')
  })
})
