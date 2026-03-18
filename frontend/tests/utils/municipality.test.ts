import { describe, it, expect } from 'vitest'
import { normalizeMunicipalityName, municipalitySlug } from '../../utils/municipality'

describe('normalizeMunicipalityName', () => {
  it('lowercases a plain ASCII name', () => {
    expect(normalizeMunicipalityName('Ljubljana')).toBe('ljubljana')
  })

  it('strips Slovenian diacritics (š → s, č → c, ž → z)', () => {
    expect(normalizeMunicipalityName('Škofja Loka')).toBe('skofja loka')
    expect(normalizeMunicipalityName('Črenšovci')).toBe('crensovci')
    expect(normalizeMunicipalityName('Žalec')).toBe('zalec')
  })

  it('handles mixed-case names with diacritics', () => {
    expect(normalizeMunicipalityName('ŠOŠTANJ')).toBe('sostanj')
  })

  it('collapses multiple spaces into one', () => {
    expect(normalizeMunicipalityName('Nova  Gorica')).toBe('nova gorica')
  })

  it('trims leading and trailing whitespace', () => {
    expect(normalizeMunicipalityName('  Koper  ')).toBe('koper')
  })

  it('replaces non-alphanumeric characters with a space', () => {
    // Hyphens and special chars become spaces; runs collapse
    expect(normalizeMunicipalityName('Murska-Sobota')).toBe('murska sobota')
  })

  it('handles names with numbers', () => {
    expect(normalizeMunicipalityName('District 9')).toBe('district 9')
  })

  it('returns empty string for empty string', () => {
    expect(normalizeMunicipalityName('')).toBe('')
  })

  it('returns empty string for null', () => {
    expect(normalizeMunicipalityName(null)).toBe('')
  })

  it('returns empty string for undefined', () => {
    expect(normalizeMunicipalityName(undefined)).toBe('')
  })

  it('normalizes a real Slovenian municipality correctly', () => {
    expect(normalizeMunicipalityName('Šempeter - Vrtojba')).toBe('sempeter vrtojba')
  })
})

describe('municipalitySlug', () => {
  it('creates a slug from a plain name', () => {
    expect(municipalitySlug('Ljubljana')).toBe('ljubljana')
  })

  it('replaces spaces with hyphens', () => {
    expect(municipalitySlug('Nova Gorica')).toBe('nova-gorica')
  })

  it('strips diacritics and slugifies', () => {
    expect(municipalitySlug('Škofja Loka')).toBe('skofja-loka')
  })

  it('handles multi-word names', () => {
    expect(municipalitySlug('Slovenske Konjice')).toBe('slovenske-konjice')
  })

  it('collapses multiple spaces into a single hyphen', () => {
    expect(municipalitySlug('Murska  Sobota')).toBe('murska-sobota')
  })

  it('returns empty string for null', () => {
    expect(municipalitySlug(null)).toBe('')
  })

  it('returns empty string for undefined', () => {
    expect(municipalitySlug(undefined)).toBe('')
  })

  it('returns empty string for empty string', () => {
    expect(municipalitySlug('')).toBe('')
  })

  it('normalizes Šempeter - Vrtojba to a clean slug', () => {
    expect(municipalitySlug('Šempeter - Vrtojba')).toBe('sempeter-vrtojba')
  })
})
