import type { GuidedAnalysisForm } from './types'
import {
  firstQueryValue,
  readQueryFlag,
  readQueryNumber,
  readQueryString,
} from '../../utils/routeQuery'

export const guidedFormRouteFields = [
  'naselje',
  'municipality',
  'ime_ko',
  'property_type',
  'lega_v_stavbi',
  'size_m2',
  'uporabna_povrsina',
  'rooms',
  'year_built',
  'floor',
  'asking_price',
  'novogradnja',
  'has_garaza',
  'has_klet',
  'has_shramba',
  'has_terasa',
  'stavba_je_dokoncana',
  'ddv_vkljucen',
  'notes',
] as const

export function createDefaultGuidedForm(): GuidedAnalysisForm {
  return {
    naselje: '',
    municipality: '',
    ime_ko: '',
    property_type: 'stanovanje',
    size_m2: 65,
    uporabna_povrsina: null,
    rooms: 2.5,
    year_built: null,
    floor: null,
    lega_v_stavbi: '',
    novogradnja: 0,
    has_garaza: 0,
    has_klet: 0,
    has_shramba: 0,
    has_terasa: 0,
    stavba_je_dokoncana: 1,
    ddv_vkljucen: 0,
    asking_price: null,
    notes: '',
  }
}

export function hasGuidedFormQuery(query: Record<string, unknown>) {
  return guidedFormRouteFields.some((field) => {
    const value = firstQueryValue(query[field])
    return value !== null && value !== ''
  })
}

export function buildGuidedFormFromQuery(query: Record<string, unknown>): GuidedAnalysisForm {
  const next = createDefaultGuidedForm()

  const naselje = readQueryString(query.naselje)
  if (naselje !== null) next.naselje = naselje

  const municipality = readQueryString(query.municipality)
  if (municipality !== null) next.municipality = municipality

  const imeKo = readQueryString(query.ime_ko)
  if (imeKo !== null) next.ime_ko = imeKo

  const propertyType = readQueryString(query.property_type)
  if (propertyType) next.property_type = propertyType

  const legaVStavbi = readQueryString(query.lega_v_stavbi)
  if (legaVStavbi !== null) next.lega_v_stavbi = legaVStavbi

  const size = readQueryNumber(query.size_m2)
  if (size !== null) next.size_m2 = size

  const uporabnaPovrsina = readQueryNumber(query.uporabna_povrsina)
  if (uporabnaPovrsina !== null) next.uporabna_povrsina = uporabnaPovrsina

  const rooms = readQueryNumber(query.rooms)
  if (rooms !== null) next.rooms = rooms

  const yearBuilt = readQueryNumber(query.year_built)
  if (yearBuilt !== null) next.year_built = yearBuilt

  const floor = readQueryNumber(query.floor)
  if (floor !== null) next.floor = floor

  const askingPrice = readQueryNumber(query.asking_price)
  if (askingPrice !== null) next.asking_price = askingPrice

  const novogradnja = readQueryFlag(query.novogradnja)
  if (novogradnja !== null) next.novogradnja = novogradnja

  const hasGaraza = readQueryFlag(query.has_garaza)
  if (hasGaraza !== null) next.has_garaza = hasGaraza

  const hasKlet = readQueryFlag(query.has_klet)
  if (hasKlet !== null) next.has_klet = hasKlet

  const hasShramba = readQueryFlag(query.has_shramba)
  if (hasShramba !== null) next.has_shramba = hasShramba

  const hasTerasa = readQueryFlag(query.has_terasa)
  if (hasTerasa !== null) next.has_terasa = hasTerasa

  const stavbaJeDokoncana = readQueryFlag(query.stavba_je_dokoncana)
  if (stavbaJeDokoncana !== null) next.stavba_je_dokoncana = stavbaJeDokoncana

  const ddvVkljucen = readQueryFlag(query.ddv_vkljucen)
  if (ddvVkljucen !== null) next.ddv_vkljucen = ddvVkljucen

  const notes = readQueryString(query.notes)
  if (notes !== null) next.notes = notes

  return next
}
