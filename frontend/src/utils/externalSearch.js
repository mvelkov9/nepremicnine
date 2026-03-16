export function buildNepremicnineSearchUrl({ municipality = '', propertyType = '', rooms = '', sizeM2 = '' } = {}) {
  const parts = ['site:nepremicnine.net/oglasi-prodaja', municipality, propertyType, rooms, sizeM2]
    .map((item) => String(item || '').trim())
    .filter(Boolean)

  return `https://www.google.com/search?q=${encodeURIComponent(parts.join(' '))}`
}
