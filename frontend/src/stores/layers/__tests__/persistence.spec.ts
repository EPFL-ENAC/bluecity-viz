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

describe('reading a saved set of municipalities', () => {
  const LAUSANNE_PULLY = { kind: 'municipalities', ofsIds: [5586, 5590] }

  it('keeps the ids and the name', () => {
    expect(pickArea({ ...LAUSANNE_PULLY, name: 'Lausanne + Pully' })).toEqual({
      kind: 'municipalities',
      ofsIds: [5586, 5590],
      name: 'Lausanne + Pully'
    })
  })

  it('sorts the ids as numbers and drops repeats', () => {
    expect(pickArea({ kind: 'municipalities', ofsIds: [5590, 10, 5586, 10] })).toEqual({
      kind: 'municipalities',
      ofsIds: [10, 5586, 5590]
    })
  })

  it('refuses an empty list, or ids that are not positive integers', () => {
    expect(pickArea({ kind: 'municipalities', ofsIds: [] })).toBeNull()
    expect(pickArea({ kind: 'municipalities' })).toBeNull()
    expect(pickArea({ kind: 'municipalities', ofsIds: '5586' })).toBeNull()
    expect(pickArea({ kind: 'municipalities', ofsIds: [5586, '5590'] })).toBeNull()
    expect(pickArea({ kind: 'municipalities', ofsIds: [5586.5] })).toBeNull()
    expect(pickArea({ kind: 'municipalities', ofsIds: [0] })).toBeNull()
    expect(pickArea({ kind: 'municipalities', ofsIds: [-1] })).toBeNull()
  })

  it('refuses more municipalities than the server takes', () => {
    const many = Array.from({ length: 101 }, (_, i) => i + 1)
    expect(pickArea({ kind: 'municipalities', ofsIds: many })).toBeNull()
    expect(pickArea({ kind: 'municipalities', ofsIds: many.slice(0, 100) })).not.toBeNull()
  })

  it('cuts a long name the same way as a circle', () => {
    expect(pickArea({ ...LAUSANNE_PULLY, name: 'x'.repeat(200) })?.name).toHaveLength(60)
    expect(pickArea({ ...LAUSANNE_PULLY, name: '  ' })?.name).toBeUndefined()
  })

  it('reads a kind it does not know as the default city', () => {
    expect(pickArea({ kind: 'polygon', ofsIds: [5586] })).toBeNull()
  })
})
