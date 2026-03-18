import { describe, it, expect } from 'vitest'
import {
  formatNumber,
  formatCurrency,
  formatPercent,
  formatDate,
  formatDateTime,
} from '../../utils/format'

// In the Nuxt test environment, useI18n() may not be fully available inside plain
// utility functions that call it outside of a component/plugin context.
// format.ts wraps the useI18n() call in try/catch and falls back to 'sl-SI', so
// the functions will still return formatted strings — we verify shape & semantics
// rather than a specific locale string.

describe('formatNumber', () => {
  it('formats a positive integer', () => {
    const result = formatNumber(1234)
    expect(typeof result).toBe('string')
    // The digits 1234 must appear (possibly with a thousands separator)
    expect(result.replace(/[^\d]/g, '')).toContain('1234')
  })

  it('formats a decimal with explicit fraction digits', () => {
    const result = formatNumber(1234.567, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    expect(typeof result).toBe('string')
    expect(result.replace(/[^\d]/g, '')).toContain('1234')
  })

  it('formats zero', () => {
    expect(formatNumber(0)).toBe('0')
  })

  it('formats a negative value', () => {
    const result = formatNumber(-500)
    expect(result).toContain('500')
    expect(result).toMatch(/-|−/) // hyphen-minus or minus sign
  })

  it('returns default fallback for null', () => {
    expect(formatNumber(null)).toBe('—')
  })

  it('returns default fallback for undefined', () => {
    expect(formatNumber(undefined)).toBe('—')
  })

  it('returns custom fallback for null', () => {
    expect(formatNumber(null, { fallback: 'N/A' })).toBe('N/A')
  })

  it('returns default fallback for NaN', () => {
    expect(formatNumber(NaN)).toBe('—')
  })
})

describe('formatCurrency', () => {
  it('formats a positive value as EUR', () => {
    const result = formatCurrency(250000)
    expect(typeof result).toBe('string')
    // Must contain the numeric digits
    expect(result.replace(/[^\d]/g, '')).toContain('250000')
    // Must contain the EUR symbol or code somewhere
    expect(result).toMatch(/€|EUR/)
  })

  it('formats zero as currency', () => {
    const result = formatCurrency(0)
    expect(result).toMatch(/€|EUR/)
    expect(result).toContain('0')
  })

  it('formats a decimal value with fraction digits', () => {
    const result = formatCurrency(1500.5, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    expect(result.replace(/[^\d]/g, '')).toContain('15005')
  })

  it('formats a negative value', () => {
    const result = formatCurrency(-100)
    expect(result).toContain('100')
    expect(result).toMatch(/€|EUR/)
  })

  it('returns default fallback for null', () => {
    expect(formatCurrency(null)).toBe('—')
  })

  it('returns default fallback for undefined', () => {
    expect(formatCurrency(undefined)).toBe('—')
  })

  it('returns custom fallback', () => {
    expect(formatCurrency(null, { fallback: '–' })).toBe('–')
  })
})

describe('formatPercent', () => {
  it('formats a decimal fraction as a percentage (scale=1)', () => {
    // 0.75 * 1 => 75%
    const result = formatPercent(0.75)
    expect(typeof result).toBe('string')
    expect(result).toContain('75')
    expect(result).toMatch(/%/)
  })

  it('formats zero', () => {
    const result = formatPercent(0)
    expect(result).toContain('0')
    expect(result).toMatch(/%/)
  })

  it('formats a negative percent', () => {
    const result = formatPercent(-0.1)
    expect(result).toContain('10')
    expect(result).toMatch(/%/)
  })

  it('respects custom scale', () => {
    // value=75, scale=0.01 => 0.75 => 75%
    const result = formatPercent(75, { scale: 0.01 })
    expect(result).toContain('75')
    expect(result).toMatch(/%/)
  })

  it('returns default fallback for null', () => {
    expect(formatPercent(null)).toBe('—')
  })

  it('returns default fallback for undefined', () => {
    expect(formatPercent(undefined)).toBe('—')
  })

  it('returns custom fallback', () => {
    expect(formatPercent(null, { fallback: '?' })).toBe('?')
  })
})

describe('formatDate', () => {
  it('formats a valid ISO date string', () => {
    const result = formatDate('2024-06-15')
    expect(typeof result).toBe('string')
    expect(result.length).toBeGreaterThan(0)
    // The year must appear somewhere
    expect(result).toContain('2024')
  })

  it('formats a Date object', () => {
    const result = formatDate(new Date('2023-01-01'))
    expect(typeof result).toBe('string')
    expect(result).toContain('2023')
  })

  it('formats with dateStyle=long', () => {
    const result = formatDate('2024-03-20', { dateStyle: 'long' })
    expect(typeof result).toBe('string')
    expect(result).toContain('2024')
  })

  it('returns default fallback for null', () => {
    expect(formatDate(null)).toBe('—')
  })

  it('returns default fallback for undefined', () => {
    expect(formatDate(undefined)).toBe('—')
  })

  it('returns default fallback for empty string', () => {
    expect(formatDate('')).toBe('—')
  })

  it('returns default fallback for invalid date string', () => {
    expect(formatDate('not-a-date')).toBe('—')
  })

  it('returns custom fallback', () => {
    expect(formatDate(null, { fallback: 'unknown' })).toBe('unknown')
  })
})

describe('formatDateTime', () => {
  it('formats a valid ISO datetime string', () => {
    const result = formatDateTime('2024-06-15T14:30:00')
    expect(typeof result).toBe('string')
    expect(result).toContain('2024')
    // Time portion should be present (hours appear as digits)
    expect(result).toMatch(/\d/)
  })

  it('formats a Date object with time', () => {
    const result = formatDateTime(new Date('2023-12-31T23:59:00'))
    expect(typeof result).toBe('string')
    expect(result).toContain('2023')
  })

  it('returns default fallback for null', () => {
    expect(formatDateTime(null)).toBe('—')
  })

  it('returns default fallback for undefined', () => {
    expect(formatDateTime(undefined)).toBe('—')
  })

  it('returns custom fallback', () => {
    expect(formatDateTime(undefined, { fallback: 'n/a' })).toBe('n/a')
  })
})
