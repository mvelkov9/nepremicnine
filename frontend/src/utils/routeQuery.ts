export function firstQueryValue(value: unknown): string | null {
  if (Array.isArray(value)) return firstQueryValue(value[0])
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return null
}

export function readQueryString(value: unknown) {
  return firstQueryValue(value)
}

export function readQueryNumber(value: unknown) {
  const scalar = firstQueryValue(value)
  if (scalar == null || scalar === '') return null

  const parsed = Number(scalar)
  return Number.isFinite(parsed) ? parsed : null
}

export function readQueryFlag(value: unknown): 0 | 1 | null {
  const scalar = firstQueryValue(value)
  if (scalar == null || scalar === '') return null

  const normalized = scalar.toLowerCase()
  if (normalized === '1' || normalized === 'true' || normalized === 'yes') return 1
  if (normalized === '0' || normalized === 'false' || normalized === 'no') return 0
  return null
}

export function readQueryTab<T extends string>(
  value: unknown,
  allowed: readonly T[],
  fallback: T,
): T {
  const scalar = firstQueryValue(value)
  return scalar && allowed.includes(scalar as T) ? (scalar as T) : fallback
}
