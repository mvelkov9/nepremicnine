const FALLBACK = '—'

function activeLocale(): string {
  try {
    const { locale } = useI18n()
    const loc = locale.value
    if (loc === 'sl') return 'sl-SI'
    if (loc === 'en') return 'en-US'
    return loc
  } catch {
    return 'sl-SI'
  }
}

export function formatNumber(
  value: number | null | undefined,
  options: {
    minimumFractionDigits?: number
    maximumFractionDigits?: number
    fallback?: string
  } = {},
): string {
  const { minimumFractionDigits = 0, maximumFractionDigits = 0, fallback = FALLBACK } = options
  if (value == null || Number.isNaN(Number(value))) return fallback
  return Number(value).toLocaleString(activeLocale(), {
    minimumFractionDigits,
    maximumFractionDigits,
  })
}

export function formatCurrency(
  value: number | null | undefined,
  options: {
    minimumFractionDigits?: number
    maximumFractionDigits?: number
    fallback?: string
  } = {},
): string {
  const { minimumFractionDigits = 0, maximumFractionDigits = 0, fallback = FALLBACK } = options
  if (value == null || Number.isNaN(Number(value))) return fallback
  return new Intl.NumberFormat(activeLocale(), {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits,
    maximumFractionDigits,
  }).format(Number(value))
}

export function formatPercent(
  value: number | null | undefined,
  options: {
    minimumFractionDigits?: number
    maximumFractionDigits?: number
    scale?: number
    fallback?: string
  } = {},
): string {
  const {
    minimumFractionDigits = 1,
    maximumFractionDigits = 1,
    scale = 1,
    fallback = FALLBACK,
  } = options
  if (value == null || Number.isNaN(Number(value))) return fallback
  return new Intl.NumberFormat(activeLocale(), {
    style: 'percent',
    minimumFractionDigits,
    maximumFractionDigits,
  }).format(Number(value) * scale)
}

export function formatDate(
  value: string | Date | null | undefined,
  options: {
    dateStyle?: 'full' | 'long' | 'medium' | 'short'
    timeStyle?: 'full' | 'long' | 'medium' | 'short'
    fallback?: string
  } = {},
): string {
  const { dateStyle = 'medium', timeStyle, fallback = FALLBACK } = options
  if (!value) return fallback
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return fallback
  return new Intl.DateTimeFormat(activeLocale(), {
    dateStyle,
    ...(timeStyle ? { timeStyle } : {}),
  }).format(date)
}

export function formatDateTime(
  value: string | Date | null | undefined,
  options: {
    dateStyle?: 'full' | 'long' | 'medium' | 'short'
    timeStyle?: 'full' | 'long' | 'medium' | 'short'
    fallback?: string
  } = {},
): string {
  return formatDate(value, { dateStyle: 'medium', timeStyle: 'short', ...options })
}
