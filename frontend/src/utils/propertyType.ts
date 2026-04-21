const FALLBACK_LABELS = {
  stanovanje: 'Stanovanje',
  hisa: 'Hisa',
  poslovni_prostor: 'Poslovni prostor',
  garaza: 'Garaza',
  turisticni: 'Turisticni',
  gostinstvo: 'Gostinstvo',
  industrijski: 'Industrijski',
  kmetijsko: 'Kmetijsko',
  parcela: 'Parcela',
}

const KNOWN_PROPERTY_TYPES = new Set(Object.keys(FALLBACK_LABELS))

function humanizePropertyType(value) {
  return String(value || '')
    .replaceAll('_', ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

export function getPropertyTypeLabel(value, t) {
  const normalizedValue = String(value || '').trim()
  if (!normalizedValue) return ''

  if (KNOWN_PROPERTY_TYPES.has(normalizedValue)) {
    const key = `propertyTypes.${normalizedValue}`
    const translated = typeof t === 'function' ? t(key) : key
    if (translated && translated !== key) {
      return translated
    }
  }

  return FALLBACK_LABELS[normalizedValue] || humanizePropertyType(normalizedValue)
}
