export function normalizeMunicipalityName(value) {
  return String(value || '')
    .trim()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

export function municipalitySlug(value) {
  return normalizeMunicipalityName(value).replace(/\s+/g, '-')
}
