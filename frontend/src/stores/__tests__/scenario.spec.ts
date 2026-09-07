import { dirOf, streetKey, useScenarioStore, type Street } from '@/stores/scenario'
import { fnv1a32, scenarioSignature } from '@/utils/scenarioHash'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

function street(lo: number, hi: number, oneway = false): Street {
  return {
    key: `${lo}-${hi}`,
    lo,
    hi,
    name: `Street ${lo}-${hi}`,
    fwdId: 0,
    bwdId: oneway ? undefined : 1,
    oneway,
    at: [6.6, 46.5],
    cls: 1
  }
}

describe('street keys', () => {
  it('names a street the same way round', () => {
    expect(streetKey(7, 3)).toBe('3-7')
    expect(streetKey(3, 7)).toBe('3-7')
  })

  it('reads the direction from the node order', () => {
    expect(dirOf(3, 7)).toBe('fwd')
    expect(dirOf(7, 3)).toBe('bwd')
  })
})

describe('scenario store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('adds, replaces and drops a street', () => {
    const store = useScenarioStore()
    expect(store.count).toBe(0)

    store.set('3-7', { action: 'remove', dir: 'both', name: 'Avenue de Cour' })
    expect(store.count).toBe(1)
    expect(store.get('3-7')?.action).toBe('remove')

    store.set('3-7', { action: '30', dir: 'fwd', name: 'Avenue de Cour' })
    expect(store.count).toBe(1)
    expect(store.get('3-7')?.action).toBe('30')

    store.remove('3-7')
    expect(store.count).toBe(0)
    expect(store.hasModifications).toBe(false)
  })

  it('drops both directions at once', () => {
    const store = useScenarioStore()
    store.set('3-7', { action: 'remove', dir: 'both', name: 'A' })
    store.remove('3-7')
    expect(store.wire).toEqual([])
  })

  it('replaces the map so watchers fire', () => {
    const store = useScenarioStore()
    const before = store.edgeModifications
    store.set('3-7', { action: 'remove', dir: 'both', name: 'A' })
    expect(store.edgeModifications).not.toBe(before)
  })

  describe('wire format', () => {
    it('sends both directed edges for a both modification', () => {
      const store = useScenarioStore()
      store.setStreets(new Map([['3-7', street(3, 7)]]))
      store.set('3-7', { action: 'remove', dir: 'both', name: 'A' })

      expect(store.wire).toEqual([
        { u: 3, v: 7, action: 'remove' },
        { u: 7, v: 3, action: 'remove' }
      ])
    })

    it('sends one edge for a one-direction modification', () => {
      const store = useScenarioStore()
      store.setStreets(new Map([['3-7', street(3, 7)]]))

      store.set('3-7', { action: '30', dir: 'fwd', name: 'A' })
      expect(store.wire).toEqual([{ u: 3, v: 7, action: 'modify', speed_kph: 30 }])

      store.setDir('3-7', 'bwd')
      expect(store.wire).toEqual([{ u: 7, v: 3, action: 'modify', speed_kph: 30 }])
    })

    it('sends only the edge a one-way street has', () => {
      const store = useScenarioStore()
      store.setStreets(new Map([['3-7', street(3, 7, true)]]))
      store.set('3-7', { action: 'remove', dir: 'both', name: 'A' })

      expect(store.wire).toEqual([{ u: 3, v: 7, action: 'remove' }])
    })

    it('translates every speed limit', () => {
      const store = useScenarioStore()
      store.setStreets(new Map([['3-7', street(3, 7, true)]]))

      for (const [action, speed] of [
        ['50', 50],
        ['30', 30],
        ['10', 10]
      ] as const) {
        store.set('3-7', { action, dir: 'both', name: 'A' })
        expect(store.wire[0]).toEqual({ u: 3, v: 7, action: 'modify', speed_kph: speed })
      }
    })

    it('sends both directions when the graph is not loaded yet', () => {
      const store = useScenarioStore()
      store.set('3-7', { action: 'remove', dir: 'both', name: 'A' })
      expect(store.wire).toHaveLength(2)
    })

    it('warns past the backend limit', () => {
      const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
      const store = useScenarioStore()
      for (let i = 0; i < 260; i++) {
        store.set(`${i}-${i + 1000}`, { action: 'remove', dir: 'both', name: `S${i}` })
      }
      expect(store.wire).toHaveLength(520)
      expect(warn).toHaveBeenCalledWith(expect.stringContaining('520'))
      warn.mockRestore()
    })
  })

  describe('hash', () => {
    it('does not depend on the order of the edits', () => {
      const store = useScenarioStore()
      store.set('3-7', { action: 'remove', dir: 'both', name: 'A' })
      store.set('1-2', { action: '30', dir: 'fwd', name: 'B' })
      const first = store.hash

      setActivePinia(createPinia())
      const other = useScenarioStore()
      other.set('1-2', { action: '30', dir: 'fwd', name: 'B' })
      other.set('3-7', { action: 'remove', dir: 'both', name: 'A' })

      expect(other.hash).toBe(first)
    })

    it('moves when the action or the direction changes', () => {
      const store = useScenarioStore()
      store.set('3-7', { action: 'remove', dir: 'both', name: 'A' })
      const removed = store.hash

      store.set('3-7', { action: '30', dir: 'both', name: 'A' })
      expect(store.hash).not.toBe(removed)

      const speed = store.hash
      store.setDir('3-7', 'fwd')
      expect(store.hash).not.toBe(speed)
    })

    it('ignores the street name', () => {
      const store = useScenarioStore()
      store.set('3-7', { action: 'remove', dir: 'both', name: 'A' })
      const withA = store.hash
      store.set('3-7', { action: 'remove', dir: 'both', name: 'Renamed' })
      expect(store.hash).toBe(withA)
    })

    it('is empty and stable with no modification', () => {
      const store = useScenarioStore()
      expect(store.signature).toBe('')
      expect(store.hash).toBe(fnv1a32(''))
    })
  })

  it('folds a one-direction entry on a one-way street to both', () => {
    const store = useScenarioStore()
    store.restore([{ key: '3-7', action: 'remove', dir: 'fwd', name: 'A' }])
    expect(store.get('3-7')?.dir).toBe('fwd')

    store.setStreets(new Map([['3-7', street(3, 7, true)]]))
    expect(store.get('3-7')?.dir).toBe('both')
  })

  it('keeps a one-direction entry on a two-way street', () => {
    const store = useScenarioStore()
    store.restore([{ key: '3-7', action: 'remove', dir: 'bwd', name: 'A' }])
    store.setStreets(new Map([['3-7', street(3, 7)]]))
    expect(store.get('3-7')?.dir).toBe('bwd')
  })

  it('round-trips through serialize and restore', () => {
    const store = useScenarioStore()
    store.set('3-7', { action: '10', dir: 'bwd', name: 'Avenue de Cour' })
    store.set('1-2', { action: 'remove', dir: 'both', name: 'Rhodanie' })

    const saved = store.serialize()
    const hash = store.hash

    setActivePinia(createPinia())
    const back = useScenarioStore()
    back.restore(saved)

    expect(back.hash).toBe(hash)
    expect(back.get('3-7')).toEqual({ action: '10', dir: 'bwd', name: 'Avenue de Cour' })
  })

  it('skips broken entries on restore', () => {
    const store = useScenarioStore()
    /* eslint-disable @typescript-eslint/no-explicit-any */
    store.restore([null, undefined, { action: 'remove' }, { key: '3-7', action: 'remove' }] as any)
    /* eslint-enable @typescript-eslint/no-explicit-any */
    expect(store.count).toBe(1)
    expect(store.get('3-7')?.dir).toBe('both')
  })

  it('sorts the dock list by street name', () => {
    const store = useScenarioStore()
    store.set('1-2', { action: 'remove', dir: 'both', name: 'Zebra' })
    store.set('3-4', { action: 'remove', dir: 'both', name: 'Alpha' })
    expect(store.list.map((r) => r.name)).toEqual(['Alpha', 'Zebra'])
  })

  it('clears the selection', () => {
    const store = useScenarioStore()
    store.select({ key: '3-7', dir: 'fwd' })
    expect(store.selected).toEqual({ key: '3-7', dir: 'fwd' })
    store.select(null)
    expect(store.selected).toBeNull()
  })

  it('does not re-set the same hovered edge', () => {
    const store = useScenarioStore()
    store.hover({ key: '3-7', dir: 'fwd' })
    const first = store.hovered
    store.hover({ key: '3-7', dir: 'fwd' })
    expect(store.hovered).toBe(first)
  })
})

describe('scenarioSignature', () => {
  it('is one sorted line per street', () => {
    const entries: Array<[string, { action: string; dir: string }]> = [
      ['3-7', { action: 'remove', dir: 'both' }],
      ['1-2', { action: '30', dir: 'fwd' }]
    ]
    expect(scenarioSignature(entries)).toBe('1-2:30:fwd|3-7:remove:both')
  })
})
