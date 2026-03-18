import { describe, it, expect } from 'vitest'
import { getPropertyTypeLabel } from '../../utils/propertyType'

// A translation function that returns the key itself to signal "no translation found",
// or a real translated string for keys we explicitly want to simulate translating.
const tMiss = (key: string) => key

// A translation function that always returns a localised string for known types
const tHit = (key: string) => {
  const translations: Record<string, string> = {
    'propertyTypes.stanovanje': 'Stanovanje (SL)',
    'propertyTypes.hisa': 'Hiša (SL)',
    'propertyTypes.poslovni_prostor': 'Poslovni prostor (SL)',
    'propertyTypes.garaza': 'Garaža (SL)',
    'propertyTypes.turisticni': 'Turistični (SL)',
    'propertyTypes.gostinstvo': 'Gostinstvo (SL)',
    'propertyTypes.industrijski': 'Industrijski (SL)',
    'propertyTypes.kmetijsko': 'Kmetijsko (SL)',
  }
  return translations[key] ?? key
}

describe('getPropertyTypeLabel — translation available', () => {
  it('returns translated label for "stanovanje"', () => {
    expect(getPropertyTypeLabel('stanovanje', tHit)).toBe('Stanovanje (SL)')
  })

  it('returns translated label for "hisa"', () => {
    expect(getPropertyTypeLabel('hisa', tHit)).toBe('Hiša (SL)')
  })

  it('returns translated label for "poslovni_prostor"', () => {
    expect(getPropertyTypeLabel('poslovni_prostor', tHit)).toBe('Poslovni prostor (SL)')
  })

  it('returns translated label for "garaza"', () => {
    expect(getPropertyTypeLabel('garaza', tHit)).toBe('Garaža (SL)')
  })

  it('returns translated label for "turisticni"', () => {
    expect(getPropertyTypeLabel('turisticni', tHit)).toBe('Turistični (SL)')
  })

  it('returns translated label for "gostinstvo"', () => {
    expect(getPropertyTypeLabel('gostinstvo', tHit)).toBe('Gostinstvo (SL)')
  })

  it('returns translated label for "industrijski"', () => {
    expect(getPropertyTypeLabel('industrijski', tHit)).toBe('Industrijski (SL)')
  })

  it('returns translated label for "kmetijsko"', () => {
    expect(getPropertyTypeLabel('kmetijsko', tHit)).toBe('Kmetijsko (SL)')
  })
})

describe('getPropertyTypeLabel — no i18n translation (t returns key)', () => {
  it('falls back to FALLBACK_LABELS for "stanovanje"', () => {
    expect(getPropertyTypeLabel('stanovanje', tMiss)).toBe('Stanovanje')
  })

  it('falls back to FALLBACK_LABELS for "hisa"', () => {
    expect(getPropertyTypeLabel('hisa', tMiss)).toBe('Hiša')
  })

  it('falls back to FALLBACK_LABELS for "poslovni_prostor"', () => {
    expect(getPropertyTypeLabel('poslovni_prostor', tMiss)).toBe('Poslovni prostor')
  })

  it('falls back to FALLBACK_LABELS for "garaza"', () => {
    expect(getPropertyTypeLabel('garaza', tMiss)).toBe('Garaža')
  })

  it('humanizes an unknown type by replacing underscores with spaces', () => {
    expect(getPropertyTypeLabel('some_unknown_type', tMiss)).toBe('some unknown type')
  })

  it('humanizes a compound unknown type', () => {
    expect(getPropertyTypeLabel('my_custom_property', tMiss)).toBe('my custom property')
  })

  it('returns the value as-is when there are no underscores', () => {
    expect(getPropertyTypeLabel('warehouse', tMiss)).toBe('warehouse')
  })
})

describe('getPropertyTypeLabel — null/empty guard', () => {
  it('returns empty string for null', () => {
    expect(getPropertyTypeLabel(null, tMiss)).toBe('')
  })

  it('returns empty string for undefined', () => {
    expect(getPropertyTypeLabel(undefined, tMiss)).toBe('')
  })

  it('returns empty string for empty string', () => {
    expect(getPropertyTypeLabel('', tMiss)).toBe('')
  })
})
