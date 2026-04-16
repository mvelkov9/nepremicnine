import { i18n } from '../i18n'

const FALLBACK = '\u2014'

function activeLocale() {
  const locale = i18n.global.locale?.value || 'sl'
  if (locale === 'sl') return 'sl-SI'
  if (locale === 'en') return 'en-US'
  return locale
}

export function formatNumber(
  value,
  { minimumFractionDigits = 0, maximumFractionDigits = 0, fallback = FALLBACK } = {},
) {
  if (value == null || Number.isNaN(Number(value))) return fallback
  return Number(value).toLocaleString(activeLocale(), {
    minimumFractionDigits,
    maximumFractionDigits,
  })
}

export function formatCurrency(
  value,
  { minimumFractionDigits = 0, maximumFractionDigits = 0, fallback = FALLBACK } = {},
) {
  if (value == null || Number.isNaN(Number(value))) return fallback
  return new Intl.NumberFormat(activeLocale(), {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits,
    maximumFractionDigits,
  }).format(Number(value))
}

export function formatPercent(
  value,
  { minimumFractionDigits = 1, maximumFractionDigits = 1, scale = 1, fallback = FALLBACK } = {},
) {
  if (value == null || Number.isNaN(Number(value))) return fallback
  return new Intl.NumberFormat(activeLocale(), {
    style: 'percent',
    minimumFractionDigits,
    maximumFractionDigits,
  }).format(Number(value) * scale)
}

export function formatDate(
  value: unknown,
  {
    dateStyle = 'medium' as Intl.DateTimeFormatOptions['dateStyle'],
    timeStyle = undefined as Intl.DateTimeFormatOptions['timeStyle'],
    fallback = FALLBACK,
  }: {
    dateStyle?: Intl.DateTimeFormatOptions['dateStyle']
    timeStyle?: Intl.DateTimeFormatOptions['timeStyle']
    fallback?: string
  } = {},
) {
  if (!value) return fallback
  const date = new Date(value as string | number | Date)
  if (Number.isNaN(date.getTime())) return fallback
  return new Intl.DateTimeFormat(activeLocale(), {
    dateStyle,
    ...(timeStyle ? { timeStyle } : {}),
  }).format(date)
}

export function formatDateTime(
  value: unknown,
  {
    dateStyle = 'medium' as Intl.DateTimeFormatOptions['dateStyle'],
    timeStyle = 'short' as Intl.DateTimeFormatOptions['timeStyle'],
    fallback = FALLBACK,
  }: {
    dateStyle?: Intl.DateTimeFormatOptions['dateStyle']
    timeStyle?: Intl.DateTimeFormatOptions['timeStyle']
    fallback?: string
  } = {},
) {
  return formatDate(value, { dateStyle, timeStyle, fallback })
}
