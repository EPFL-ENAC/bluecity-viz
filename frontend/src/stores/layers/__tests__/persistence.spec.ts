import { pickArea, pickTrafficInputs } from '@/stores/layers/persistence'
import { describe, expect, it } from 'vitest'

const LAUSANNE = { kind: 'circle', lon: 6.632, lat: 46.52, radiusM: 3000 }

describe('reading a saved area', () => {
  it('keeps the name the picker wrote', () => {
    expect(pickArea({ ...LAUSANNE, name: 'East Lausanne' })?.name).toBe('East Lausanne')
  })

  it('has no name for an area saved before we had one', () => {
    expect(pickArea(LAUSANNE)?.name).toBeUndefined()
  })

  it('drops a name that is not a real one', () => {
    expect(pickArea({ ...LAUSANNE, name: '   ' })?.name).toBeUndefined()
    expect(pickArea({ ...LAUSANNE, name: 42 })?.name).toBeUndefined()
  })

  it('cuts a name longer than the dock', () => {
    const long = 'x'.repeat(200)
    expect(pickArea({ ...LAUSANNE, name: long })?.name).toHaveLength(60)
  })

  it('still refuses a circle outside the country', () => {
    expect(pickArea({ ...LAUSANNE, lon: 2.35, name: 'Paris' })).toBeNull()
  })
})

describe('reading the node weighting', () => {
  it('keeps population', () => {
    expect(pickTrafficInputs({ nodeWeighting: 'population' }).nodeWeighting).toBe('population')
  })

  it('reads an old save or an unknown value as uniform', () => {
    expect(pickTrafficInputs({}).nodeWeighting).toBe('uniform')
    expect(pickTrafficInputs({ nodeWeighting: 'cats' }).nodeWeighting).toBe('uniform')
  })
})
