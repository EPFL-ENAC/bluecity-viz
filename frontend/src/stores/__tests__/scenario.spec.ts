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
    cls: 1,
    bus: false
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
    store.select({ keys: ['3-7'], dir: 'fwd' })
    expect(store.selected).toEqual({ keys: ['3-7'], dir: 'fwd' })
    store.select(null)
    expect(store.selected).toBeNull()
  })

  it('takes an empty selection for none', () => {
    const store = useScenarioStore()
    store.select({ keys: [], dir: 'both' })
    expect(store.selected).toBeNull()
  })

  it('does not re-set the same hovered streets', () => {
    const store = useScenarioStore()
    store.hover({ keys: ['3-7'], dir: 'fwd' })
    const first = store.hovered
    store.hover({ keys: ['3-7'], dir: 'fwd' })
    expect(store.hovered).toBe(first)
  })

  it('re-sets the hover when the streets differ', () => {
    const store = useScenarioStore()
    store.hover({ keys: ['3-7'], dir: 'both' })
    const first = store.hovered
    store.hover({ keys: ['3-7', '1-2'], dir: 'both' })
    expect(store.hovered).not.toBe(first)
    expect(store.hoveredSet.has('1-2')).toBe(true)
  })
})

describe('the selection', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('adds a street on shift-click and takes it back out', () => {
    const store = useScenarioStore()
    store.toggleSelected('1-2')
    store.toggleSelected('3-4')
    expect(store.selected?.keys).toEqual(['1-2', '3-4'])
    store.toggleSelected('1-2')
    expect(store.selected?.keys).toEqual(['3-4'])
    store.toggleSelected('3-4')
    expect(store.selected).toBeNull()
  })

  it('keeps the direction while toggling', () => {
    const store = useScenarioStore()
    store.select({ keys: ['1-2'], dir: 'fwd' })
    store.toggleSelected('3-4')
    expect(store.selected?.dir).toBe('fwd')
  })

  it('adds a stroke in order, without repeats', () => {
    const store = useScenarioStore()
    store.addSelected(['1-2', '3-4'])
    store.addSelected(['3-4', '5-6'])
    expect(store.selected?.keys).toEqual(['1-2', '3-4', '5-6'])
  })

  it('does not touch the selection when a stroke catches nothing new', () => {
    const store = useScenarioStore()
    store.addSelected(['1-2'])
    const first = store.selected
    store.addSelected(['1-2'])
    expect(store.selected).toBe(first)
  })

  it('moves the whole selection onto one direction', () => {
    const store = useScenarioStore()
    store.select({ keys: ['1-2', '3-4'], dir: 'both' })
    store.setSelectedDir('bwd')
    expect(store.selected).toEqual({ keys: ['1-2', '3-4'], dir: 'bwd' })
  })

  it('lists the selected streets as a set', () => {
    const store = useScenarioStore()
    store.select({ keys: ['1-2', '3-4'], dir: 'both' })
    expect(store.selectedSet.has('3-4')).toBe(true)
    expect(store.selectedSet.has('9-9')).toBe(false)
  })
})

describe('writing several streets at once', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('replaces the map once for the whole batch', () => {
    const store = useScenarioStore()
    const before = store.edgeModifications
    store.setMany([
      ['1-2', { action: '30', dir: 'both', name: 'A' }],
      ['3-4', { action: '30', dir: 'both', name: 'B' }]
    ])
    expect(store.edgeModifications).not.toBe(before)
    expect(store.count).toBe(2)
  })

  it('folds a one-way street to both directions', () => {
    const store = useScenarioStore()
    store.setStreets(new Map([['1-2', street(1, 2, true)]]))
    store.setMany([['1-2', { action: 'remove', dir: 'fwd', name: 'A' }]])
    expect(store.get('1-2')?.dir).toBe('both')
  })

  it('drops several streets at once', () => {
    const store = useScenarioStore()
    store.setMany([
      ['1-2', { action: '30', dir: 'both', name: 'A' }],
      ['3-4', { action: '30', dir: 'both', name: 'B' }]
    ])
    store.removeMany(['1-2', '9-9'])
    expect(store.count).toBe(1)
    expect(store.get('3-4')).toBeDefined()
  })

  it('does nothing when none of the streets are there', () => {
    const store = useScenarioStore()
    store.set('1-2', { action: '30', dir: 'both', name: 'A' })
    const before = store.edgeModifications
    store.removeMany(['9-9'])
    expect(store.edgeModifications).toBe(before)
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

describe('groups', () => {
  beforeEach(() => setActivePinia(createPinia()))

  function twoStreets() {
    const store = useScenarioStore()
    store.setStreets(
      new Map([
        ['1-2', street(1, 2)],
        ['3-4', street(3, 4)]
      ])
    )
    store.setMany([
      ['1-2', { action: '30', dir: 'both', name: 'A', group: 'g1' }],
      ['3-4', { action: '30', dir: 'both', name: 'B', group: 'g1' }]
    ])
    return store
  }

  it('gathers the streets of one group', () => {
    const store = twoStreets()
    const group = store.groups.get('g1')
    expect(group?.keys).toEqual(['1-2', '3-4'])
    expect(group?.action).toBe('30')
    expect(group?.label).toBe('2 streets')
    expect(group?.anyTwoWay).toBe(true)
  })

  it('takes the direction from a street that has two lanes', () => {
    const store = useScenarioStore()
    store.setStreets(
      new Map([
        ['1-2', street(1, 2, true)],
        ['3-4', street(3, 4)]
      ])
    )
    store.setMany([
      ['1-2', { action: '30', dir: 'both', name: 'One way', group: 'g1' }],
      ['3-4', { action: '30', dir: 'fwd', name: 'Two way', group: 'g1' }]
    ])
    expect(store.groups.get('g1')?.dir).toBe('fwd')
  })

  it('moves every street of the group at once', () => {
    const store = twoStreets()
    store.setGroup('g1', { action: 'remove' })
    expect(store.get('1-2')?.action).toBe('remove')
    expect(store.get('3-4')?.action).toBe('remove')
  })

  it('does nothing for a group that is not there', () => {
    const store = twoStreets()
    const before = store.edgeModifications
    store.setGroup('g9', { action: 'remove' })
    expect(store.edgeModifications).toBe(before)
  })

  it('drops the whole group', () => {
    const store = twoStreets()
    store.set('5-6', { action: '10', dir: 'both', name: 'Alone' })
    store.removeGroup('g1')
    expect(store.count).toBe(1)
    expect(store.get('5-6')).toBeDefined()
  })

  it('gives a fresh id past the groups already there', () => {
    const store = useScenarioStore()
    store.restore([
      { key: '1-2', action: '30', dir: 'both', name: 'A', group: 'g3' },
      { key: '3-4', action: '30', dir: 'both', name: 'B' }
    ])
    expect(store.newGroupId()).toBe('g4')
  })

  it('lists the groups first, then the lone streets by name', () => {
    const store = twoStreets()
    store.set('5-6', { action: '10', dir: 'both', name: 'Zebra' })
    store.set('7-8', { action: '10', dir: 'both', name: 'Alpha' })
    const rows = store.dockRows
    expect(rows[0].kind).toBe('group')
    expect(rows.slice(1).map((row) => (row.kind === 'street' ? row.name : ''))).toEqual([
      'Alpha',
      'Zebra'
    ])
  })

  it('leaves the hash alone: a group changes nothing on the wire', () => {
    const store = twoStreets()
    const before = store.hash
    store.setGroup('g1', { action: '30' })
    expect(store.hash).toBe(before)

    // the same two streets with no group at all hash the same way
    store.setMany([
      ['1-2', { action: '30', dir: 'both', name: 'A' }],
      ['3-4', { action: '30', dir: 'both', name: 'B' }]
    ])
    expect(store.groups.size).toBe(0)
    expect(store.hash).toBe(before)
  })

  it('writes no group field when there is none', () => {
    const store = useScenarioStore()
    store.set('1-2', { action: '30', dir: 'both', name: 'A' })
    expect(store.serialize()).toEqual([{ key: '1-2', action: '30', dir: 'both', name: 'A' }])
  })

  it('round-trips a group through serialize and restore', () => {
    const store = twoStreets()
    const saved = store.serialize()
    store.clear()
    store.restore(saved)
    expect(store.groups.get('g1')?.keys).toEqual(['1-2', '3-4'])
  })

  it('restores an old scenario that has no group', () => {
    const store = useScenarioStore()
    store.restore([{ key: '1-2', action: '30', dir: 'both', name: 'A' }])
    expect(store.get('1-2')?.group).toBeUndefined()
    expect(store.groups.size).toBe(0)
    expect(store.dockRows).toHaveLength(1)
  })
})
