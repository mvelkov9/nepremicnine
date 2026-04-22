import { municipalitySlug } from '../../utils/municipality'
import { readQueryString } from '../../utils/routeQuery'

interface CompareRouteQuery {
  compare_a?: unknown
  compare_b?: unknown
  compare_c?: unknown
  compare?: unknown
}

function compareTokens(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.flatMap((entry) => compareTokens(entry))
  }

  const scalar = readQueryString(value)
  if (!scalar) return []

  return scalar
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

export function buildCanonicalCompareSlots(
  query: CompareRouteQuery,
  validMunicipalities: readonly string[],
) {
  const validSet = new Set(validMunicipalities)
  const slugLookup = new Map(validMunicipalities.map((item) => [municipalitySlug(item), item]))

  function normalizeValue(value: string | null) {
    if (!value) return ''
    if (validSet.has(value)) return value
    return slugLookup.get(value) || ''
  }

  const combined = [
    normalizeValue(readQueryString(query.compare_a)),
    normalizeValue(readQueryString(query.compare_b)),
    normalizeValue(readQueryString(query.compare_c)),
    ...compareTokens(query.compare).map((value) => normalizeValue(value)),
  ]
    .filter(Boolean)
    .filter((value, index, items) => items.indexOf(value) === index)
    .slice(0, 3)

  return {
    compareA: combined[0] || '',
    compareB: combined[1] || '',
    compareC: combined[2] || '',
  }
}
