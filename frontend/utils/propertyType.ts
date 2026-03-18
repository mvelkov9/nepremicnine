const FALLBACK_LABELS: Record<string, string> = {
  stanovanje: 'Stanovanje',
  hisa: 'Hiša',
  poslovni_prostor: 'Poslovni prostor',
  garaza: 'Garaža',
  turisticni: 'Turistični',
  gostinstvo: 'Gostinstvo',
  industrijski: 'Industrijski',
  kmetijsko: 'Kmetijsko',
}

function humanize(value: string): string {
  return value.replaceAll('_', ' ').replace(/\s+/g, ' ').trim()
}

export function getPropertyTypeLabel(
  value: string | null | undefined,
  t: (key: string) => string,
): string {
  if (!value) return ''
  const key = `propertyTypes.${value}`
  const translated = t(key)
  if (translated && translated !== key) return translated
  return FALLBACK_LABELS[value] || humanize(value)
}
