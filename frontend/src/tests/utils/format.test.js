import { describe, it, expect } from 'vitest'
import { formatNumber, formatCurrency, formatPercent, formatDate } from '@/utils/format'

describe('formatNumber', () => {
  it('returns fallback for null', () => {
    expect(formatNumber(null)).toBe('—')
  })

  it('returns fallback for undefined', () => {
    expect(formatNumber(undefined)).toBe('—')
  })

  it('returns fallback for NaN string', () => {
    expect(formatNumber('not-a-number')).toBe('—')
  })

  it('formats zero', () => {
    expect(formatNumber(0)).toMatch(/^0$/)
  })

  it('formats integer', () => {
    const result = formatNumber(1000)
    expect(result).toBeTruthy()
    expect(result).not.toBe('—')
  })

  it('respects custom fallback', () => {
    expect(formatNumber(null, { fallback: 'N/A' })).toBe('N/A')
  })
})

describe('formatCurrency', () => {
  it('returns fallback for null', () => {
    expect(formatCurrency(null)).toBe('—')
  })

  it('returns fallback for undefined', () => {
    expect(formatCurrency(undefined)).toBe('—')
  })

  it('formats a euro amount', () => {
    const result = formatCurrency(250000)
    expect(result).toContain('250')
    expect(result).not.toBe('—')
  })

  it('includes EUR symbol or code', () => {
    const result = formatCurrency(100)
    expect(result).toMatch(/€|EUR/)
  })
})

describe('formatPercent', () => {
  it('returns fallback for null', () => {
    expect(formatPercent(null)).toBe('—')
  })

  it('formats a decimal as percent', () => {
    const result = formatPercent(0.123)
    expect(result).toContain('12')
    expect(result).not.toBe('—')
  })

  it('includes percent sign', () => {
    const result = formatPercent(0.5)
    expect(result).toContain('%')
  })
})

describe('formatDate', () => {
  it('returns fallback for null', () => {
    expect(formatDate(null)).toBe('—')
  })

  it('returns fallback for empty string', () => {
    expect(formatDate('')).toBe('—')
  })

  it('returns fallback for invalid date', () => {
    expect(formatDate('not-a-date')).toBe('—')
  })

  it('formats a valid ISO date string', () => {
    const result = formatDate('2024-06-15')
    expect(result).toBeTruthy()
    expect(result).not.toBe('—')
  })
})
