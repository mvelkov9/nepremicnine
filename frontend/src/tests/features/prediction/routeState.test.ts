import { describe, expect, it } from 'vitest'
import {
  buildPredictionFormFromQuery,
  createDefaultPredictionForm,
  hasPredictionRouteState,
} from '../../../features/prediction/routeState'

describe('prediction routeState', () => {
  it('builds a full prediction form from route query values', () => {
    const form = buildPredictionFormFromQuery({
      municipality: 'Ljubljana',
      naselje: 'Center',
      property_type: 'hisa',
      size_m2: '120.5',
      rooms: '4',
      year_built: '2008',
      floor: '2',
      latitude: '46.05',
      longitude: '14.51',
      uporabna_povrsina: '98.7',
      ime_ko: '1234',
      lega_v_stavbi: 'sredina',
      novogradnja: '1',
      has_garaza: '1',
      has_klet: '0',
      has_shramba: '1',
      has_terasa: '0',
      stavba_je_dokoncana: '0',
      ddv_vkljucen: '1',
    })

    expect(form).toMatchObject({
      municipality: 'Ljubljana',
      naselje: 'Center',
      property_type: 'hisa',
      size_m2: 120.5,
      rooms: 4,
      year_built: 2008,
      floor: 2,
      latitude: 46.05,
      longitude: 14.51,
      uporabna_povrsina: 98.7,
      ime_ko: '1234',
      lega_v_stavbi: 'sredina',
      novogradnja: 1,
      has_garaza: 1,
      has_klet: 0,
      has_shramba: 1,
      has_terasa: 0,
      stavba_je_dokoncana: 0,
      ddv_vkljucen: 1,
    })
  })

  it('resets unspecified route fields back to defaults', () => {
    const defaults = createDefaultPredictionForm()
    const form = buildPredictionFormFromQuery({
      municipality: 'Maribor',
      size_m2: '70',
    })

    expect(form).toEqual({
      ...defaults,
      municipality: 'Maribor',
      size_m2: 70,
    })
  })

  it('ignores tab-only route changes when checking for scenario state', () => {
    expect(hasPredictionRouteState({ tab: 'history' })).toBe(false)
    expect(hasPredictionRouteState({ municipality: 'Celje' })).toBe(true)
  })
})
