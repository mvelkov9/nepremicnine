import { normalizeMunicipalityName } from './municipality'

const PROPERTY_TYPE_SLUGS = {
  stanovanje: 'stanovanje',
  hisa: 'hisa',
  poslovni_prostor: 'poslovni-prostor',
  garaza: 'garaza',
}

function slugify(value = '') {
  return normalizeMunicipalityName(value).replace(/\s+/g, '-')
}

function regionSlug(value = '') {
  return slugify(value)
}

function propertySlug(value = '') {
  const normalized = normalizeMunicipalityName(value)
  return PROPERTY_TYPE_SLUGS[normalized] || ''
}

export function buildNepremicnineSearchUrl({
  municipality = '',
  statisticalRegion = '',
  propertyType = '',
} = {}) {
  const municipalitySlug = slugify(municipality)
  const region = regionSlug(statisticalRegion)
  const type = propertySlug(propertyType)

  if (region && municipalitySlug && type) {
    return `https://www.nepremicnine.net/oglasi-prodaja/${region}/${municipalitySlug}/${type}/`
  }

  if (region && municipalitySlug) {
    return `https://www.nepremicnine.net/oglasi-prodaja/${region}/${municipalitySlug}/`
  }

  if (municipalitySlug && type) {
    return `https://www.nepremicnine.net/oglasi-prodaja/${municipalitySlug}/${type}/`
  }

  if (municipalitySlug) {
    return `https://www.nepremicnine.net/oglasi-prodaja/${municipalitySlug}/`
  }

  if (type) {
    return `https://www.nepremicnine.net/oglasi-prodaja/${type}/`
  }

  return 'https://www.nepremicnine.net/oglasi-prodaja/'
}
