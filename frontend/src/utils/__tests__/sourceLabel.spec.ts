import { splitSourceLabel } from '@/utils/sourceLabel'
import { describe, expect, it } from 'vitest'

describe('splitSourceLabel', () => {
  it('splits the SP code out of the name', () => {
    expect(splitSourceLabel('Urban Accessibility Atlas - SP2')).toEqual({
      name: 'Urban Accessibility Atlas',
      sp: 'SP2'
    })
  })

  it('keeps a non-SP qualifier in the name', () => {
    expect(splitSourceLabel('Habitat Density - Biodiversity')).toEqual({
      name: 'Habitat Density (Biodiversity)',
      sp: '—'
    })
  })

  it('leaves a label without a dash alone', () => {
    expect(splitSourceLabel('Population & Waste Correlation Data')).toEqual({
      name: 'Population & Waste Correlation Data',
      sp: '—'
    })
  })
})
