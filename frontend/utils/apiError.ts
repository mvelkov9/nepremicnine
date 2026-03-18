const DETAIL_KEY_MAP: Record<string, string> = {
  'No trained model found': 'errorDetail.noTrainedModel',
  'No trained model': 'errorDetail.noTrainedModel',
  'No trained model. Train first.': 'errorDetail.noTrainedModel',
  'CSV not found': 'errorDetail.csvNotFound',
  'Job not found': 'errorDetail.jobNotFound',
  'A training job is already queued or running': 'errorDetail.trainingAlreadyRunning',
  'Registration failed': 'errorDetail.registrationFailed',
  'Invalid credentials': 'errorDetail.invalidCredentials',
  'Account disabled': 'errorDetail.accountDisabled',
  'Invalid refresh token': 'errorDetail.invalidRefreshToken',
  'Refresh token has been revoked': 'errorDetail.invalidRefreshToken',
  'Cannot modify own account': 'errorDetail.cannotModifyOwnAccount',
  'Cannot delete own account': 'errorDetail.cannotDeleteOwnAccount',
  'Invalid role': 'errorDetail.invalidRole',
  'Path is outside the allowed data directory': 'errorDetail.invalidPath',
  'Symbolic links are not allowed': 'errorDetail.invalidPath',
  'Data preparation failed. Check server logs.': 'errorDetail.prepareFailed',
  'No profile changes submitted': 'errorDetail.noProfileChanges',
  'Full name is required': 'errorDetail.fullNameRequired',
  'Invalid avatar URL': 'errorDetail.invalidAvatarUrl',
}

interface ApiError {
  response?: { status?: number; data?: { detail?: string } }
  code?: string
  message?: string
}

type TranslateFunction = (key: string, values?: Record<string, unknown>) => string

function translateDetail(detail: string, t: TranslateFunction): string {
  const mappedKey = DETAIL_KEY_MAP[detail]
  if (mappedKey) return t(mappedKey)

  if (detail.startsWith('File exceeds')) {
    const limit = detail.match(/(\d+)/)?.[1]
    return t('errorDetail.fileTooLarge', { limit: limit || '?' })
  }

  if (detail.startsWith("File type '")) return t('errorDetail.unsupportedFileType')

  return detail
}

export function getApiErrorMessage(error: unknown, t: TranslateFunction): string {
  const apiError = (error ?? {}) as ApiError
  const status = apiError.response?.status
  const detail = apiError.response?.data?.detail

  if (detail) return translateDetail(detail, t)
  if (apiError.code === 'ECONNABORTED') return t('error.timeout')
  if (status === 401) return t('error.unauthorized')
  if (status === 403) return t('error.forbidden')
  if (status === 404) return t('error.notFound')
  if (status === 413) return t('errorDetail.fileTooLarge', { limit: '?' })
  if (status === 429) return t('error.rateLimited')
  if (status && status >= 500) return t('error.server')
  return apiError.message || t('common.error')
}

export type { ApiError }
