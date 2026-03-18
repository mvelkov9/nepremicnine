import { describe, expect, it } from 'vitest'
import { getApiErrorMessage } from './apiError'

describe('getApiErrorMessage', () => {
  const t = (key) => key

  it('returns backend detail when present', () => {
    const error = {
      response: {
        data: {
          detail: 'Detailed backend message',
        },
      },
    }

    expect(getApiErrorMessage(error, t)).toBe('Detailed backend message')
  })

  it('falls back to translation for generic failures', () => {
    expect(getApiErrorMessage({}, t)).toBe('common.error')
  })
})
