const FALLBACK_LABELS = {
  stanovanje: 'Stanovanje',
  hisa: 'Hisa',
  poslovni_prostor: 'Poslovni prostor',
  garaza: 'Garaza',
  turisticni: 'Turisticni',
  gostinstvo: 'Gostinstvo',
  industrijski: 'Industrijski',
  kmetijsko: 'Kmetijsko',
}

function humanizePropertyType(value) {
  return String(value || '')
    .replaceAll('_', ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

export function getPropertyTypeLabel(value, t) {
  if (!value) return ''
  const key = `propertyTypes.${value}`
  const translated = typeof t === 'function' ? t(key) : key
  if (translated && translated !== key) {
    return translated
  }
  return FALLBACK_LABELS[value] || humanizePropertyType(value)
}
