import { describe, expect, it } from 'vitest'
import { buildCanonicalCompareSlots } from '../../../features/municipalities/compareState'

describe('municipalities compareState', () => {
  const municipalities = ['Ljubljana', 'Maribor', 'Celje', 'Novo mesto']

  it('keeps direct compare slot values when they are already canonical', () => {
    expect(
      buildCanonicalCompareSlots(
        {
          compare_a: 'Ljubljana',
          compare_b: 'Maribor',
          compare_c: 'Celje',
        },
        municipalities,
      ),
    ).toEqual({
      compareA: 'Ljubljana',
      compareB: 'Maribor',
      compareC: 'Celje',
    })
  })

  it('accepts legacy comma-separated compare slugs and maps them back to municipality names', () => {
    expect(
      buildCanonicalCompareSlots(
        {
          compare: 'ljubljana,maribor,novo-mesto',
        },
        municipalities,
      ),
    ).toEqual({
      compareA: 'Ljubljana',
      compareB: 'Maribor',
      compareC: 'Novo mesto',
    })
  })

  it('deduplicates and limits compare values to three slots', () => {
    expect(
      buildCanonicalCompareSlots(
        {
          compare_a: 'Ljubljana',
          compare: 'ljubljana,maribor,celje,novo-mesto',
        },
        municipalities,
      ),
    ).toEqual({
      compareA: 'Ljubljana',
      compareB: 'Maribor',
      compareC: 'Celje',
    })
  })
})
