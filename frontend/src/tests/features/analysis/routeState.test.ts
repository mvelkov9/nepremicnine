import { describe, expect, it } from 'vitest'
import {
  buildGuidedFormFromQuery,
  createDefaultGuidedForm,
  hasGuidedFormQuery,
} from '../../../features/analysis/routeState'

describe('analysis routeState', () => {
  it('builds the guided analysis form from saved query values', () => {
    const form = buildGuidedFormFromQuery({
      municipality: 'Ljubljana',
      naselje: 'Center',
      property_type: 'hisa',
      size_m2: '135',
      uporabna_povrsina: '118',
      rooms: '5',
      year_built: '2012',
      floor: '1',
      lega_v_stavbi: 'vrh',
      asking_price: '450000',
      novogradnja: '1',
      has_garaza: '1',
      has_klet: '0',
      has_shramba: '1',
      has_terasa: '1',
      stavba_je_dokoncana: '1',
      ddv_vkljucen: '0',
    })

    expect(form).toMatchObject({
      municipality: 'Ljubljana',
      naselje: 'Center',
      property_type: 'hisa',
      size_m2: 135,
      uporabna_povrsina: 118,
      rooms: 5,
      year_built: 2012,
      floor: 1,
      lega_v_stavbi: 'vrh',
      asking_price: 450000,
      novogradnja: 1,
      has_garaza: 1,
      has_klet: 0,
      has_shramba: 1,
      has_terasa: 1,
      stavba_je_dokoncana: 1,
      ddv_vkljucen: 0,
    })
  })

  it('falls back to guided defaults for missing query fields', () => {
    const defaults = createDefaultGuidedForm()
    const form = buildGuidedFormFromQuery({
      municipality: 'Koper',
      asking_price: '310000',
    })

    expect(form).toEqual({
      ...defaults,
      municipality: 'Koper',
      asking_price: 310000,
    })
  })

  it('treats tab-only route changes as non-scenario updates', () => {
    expect(hasGuidedFormQuery({ tab: 'results' })).toBe(false)
    expect(hasGuidedFormQuery({ municipality: 'Novo mesto' })).toBe(true)
  })
})
