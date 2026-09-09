import type { EdgeModification } from '@/services/trafficAnalysis'
import { scenarioHash, scenarioSignature } from '@/utils/scenarioHash'
import { defineStore } from 'pinia'
import { computed, markRaw, ref, shallowRef } from 'vue'

/** What was done to a street. Colour never says this, ink and shape do. */
export type ScenarioAction = 'remove' | '50' | '30' | '10'

/**
 * Which directed edges the action applies to.
 *
 * A two-way street is two directed edges in the graph. `fwd` is the edge that
 * goes from the smaller node id to the bigger one, `bwd` the other way. That
 * choice is arbitrary but stable: it does not depend on the geometry, so it
 * survives a reload and a shared link.
 */
export type ScenarioDir = 'both' | 'fwd' | 'bwd'

/**
 * How the pointer selects streets.
 *
 * `pointer` is the plain click. `lasso` draws a shape and takes what it holds,
 * `brush` paints along the streets. Both drag, so they take the map drag while
 * they are on.
 */
export type SelectTool = 'pointer' | 'lasso' | 'brush'

export interface StreetMod {
  action: ScenarioAction
  dir: ScenarioDir
  name: string
}

/** One street of the graph, both of its directed edges. */
export interface Street {
  key: string
  lo: number
  hi: number
  name: string
  /** feature index of the lo -> hi edge, when the graph has it */
  fwdId?: number
  /** feature index of the hi -> lo edge, when the graph has it */
  bwdId?: number
  oneway: boolean
  /** midpoint, where the badge sits */
  at: [number, number]
  cls: number
  speed?: number
  /** at least one bus line uses it, for the "bus routes only" filter */
  bus: boolean
}

/**
 * The streets pointed at together: a click, a lasso stroke, a dock row.
 *
 * One selection, one direction. Editing several streets at once means the
 * same action on all of them, which is what a group is.
 */
export interface StreetRef {
  keys: string[]
  dir: ScenarioDir
}

/** Same streets, same order, same direction. */
export function sameRef(a: StreetRef | null, b: StreetRef | null): boolean {
  if (a === b) return true
  if (!a || !b) return false
  if (a.dir !== b.dir || a.keys.length !== b.keys.length) return false
  return a.keys.every((key, index) => key === b.keys[index])
}

/** The two nodes of a street, smaller first. Same key both ways round. */
export function streetKey(u: number, v: number): string {
  return u <= v ? `${u}-${v}` : `${v}-${u}`
}

/** The direction of the directed edge u -> v inside its street. */
export function dirOf(u: number, v: number): 'fwd' | 'bwd' {
  return u <= v ? 'fwd' : 'bwd'
}

const SPEEDS: Record<string, number> = { '50': 50, '30': 30, '10': 10 }

/** The backend takes 500 directed modifications at most. */
export const MAX_WIRE_MODIFICATIONS = 500

/**
 * The modified graph, shared by every tool.
 *
 * The scenario belongs to no tool: routing and waste collection both read it,
 * each keeps its own result, and a result goes stale when the hash moves.
 */
export const useScenarioStore = defineStore('scenario', () => {
  /** street key -> what was done to it */
  const edgeModifications = ref<Map<string, StreetMod>>(new Map())

  /** the whole workbench (both tools live in one dock) */
  const isOpen = ref(false)
  const activeTab = ref<'routing' | 'cvrp'>('routing')

  /** the streets picked by a click, a lasso or a brush, with their popover */
  const selected = ref<StreetRef | null>(null)
  /** shared by the dock rows and the map, so hovering one lights the other */
  const hovered = ref<StreetRef | null>(null)
  const mapMode = ref<'scenario' | 'result'>('scenario')

  /** Which gesture the pointer is doing on the map. */
  const tool = ref<SelectTool>('pointer')
  /** How wide the brush paints, in screen pixels. */
  const brushRadius = ref(24)

  /**
   * The streets of the loaded graph, filled by useGraphEdges.
   *
   * markRaw and shallowRef on purpose. This map holds one entry per street of
   * the whole city, and Pinia's devtools plugin deep watches every store: on
   * each mutation it walks the entire state. With 10k reactive streets in it,
   * one hover cost 60 ms in dev. Nothing here is ever changed in place, the
   * map is replaced whole, so reactivity on the entries buys us nothing.
   */
  const streets = shallowRef<Map<string, Street>>(markRaw(new Map()))

  /** For the map and the dock rows, which ask "is this one of them?". */
  const selectedSet = computed(() => new Set(selected.value?.keys ?? []))
  const hoveredSet = computed(() => new Set(hovered.value?.keys ?? []))

  const count = computed(() => edgeModifications.value.size)
  const hasModifications = computed(() => edgeModifications.value.size > 0)

  const signature = computed(() => scenarioSignature(edgeModifications.value.entries()))
  const hash = computed(() => scenarioHash(edgeModifications.value.entries()))

  /** The list the dock shows, by name. */
  const list = computed(() => {
    const rows = Array.from(edgeModifications.value.entries()).map(([key, mod]) => ({
      key,
      ...mod
    }))
    return rows.sort((a, b) => a.name.localeCompare(b.name))
  })

  /**
   * The backend format. It only knows directed edges, so 'both' becomes two
   * entries. A one-way street contributes the single edge it has.
   */
  const wire = computed<EdgeModification[]>(() => {
    const out: EdgeModification[] = []

    for (const [key, mod] of edgeModifications.value) {
      const [lo, hi] = key.split('-').map(Number)
      const street = streets.value.get(key)

      const pairs: Array<[number, number]> = []
      // Without the graph we cannot tell a one-way street from a two-way one,
      // so send both directions and let the backend skip the missing edge.
      const hasFwd = !street || street.fwdId !== undefined
      const hasBwd = !street || street.bwdId !== undefined
      if (mod.dir !== 'bwd' && hasFwd) pairs.push([lo, hi])
      if (mod.dir !== 'fwd' && hasBwd) pairs.push([hi, lo])

      for (const [u, v] of pairs) {
        if (mod.action === 'remove') {
          out.push({ u, v, action: 'remove' })
        } else {
          out.push({ u, v, action: 'modify', speed_kph: SPEEDS[mod.action] })
        }
      }
    }

    if (out.length > MAX_WIRE_MODIFICATIONS) {
      console.warn(
        `The scenario has ${out.length} directed modifications, the backend takes ${MAX_WIRE_MODIFICATIONS}.`
      )
    }
    return out
  })

  function get(key: string): StreetMod | undefined {
    return edgeModifications.value.get(key)
  }

  // Always a new Map: the watchers that persist and redraw compare identity.
  function set(key: string, mod: StreetMod): void {
    const next = new Map(edgeModifications.value)
    next.set(key, mod)
    edgeModifications.value = next
  }

  /** Drop a street, both directions at once. */
  function remove(key: string): void {
    if (!edgeModifications.value.has(key)) return
    const next = new Map(edgeModifications.value)
    next.delete(key)
    edgeModifications.value = next
  }

  /** Several streets in one go, so the watchers that persist and redraw run once. */
  function setMany(entries: Array<[string, StreetMod]>): void {
    if (entries.length === 0) return
    const next = new Map(edgeModifications.value)
    for (const [key, mod] of entries) next.set(key, mod)
    edgeModifications.value = next
    normalizeOneWay()
  }

  function removeMany(keys: string[]): void {
    const next = new Map(edgeModifications.value)
    let changed = false
    for (const key of keys) if (next.delete(key)) changed = true
    if (!changed) return
    edgeModifications.value = next
  }

  function setDir(key: string, dir: ScenarioDir): void {
    const mod = edgeModifications.value.get(key)
    if (!mod) return
    set(key, { ...mod, dir })
  }

  function clear(): void {
    if (edgeModifications.value.size === 0) return
    edgeModifications.value = new Map()
  }

  function select(ref_: StreetRef | null): void {
    selected.value = ref_ && ref_.keys.length > 0 ? ref_ : null
  }

  /** Shift-click: put the street in, or take it out when it was already in. */
  function toggleSelected(key: string): void {
    const now = selected.value
    if (!now) {
      selected.value = { keys: [key], dir: 'both' }
      return
    }
    const keys = now.keys.includes(key)
      ? now.keys.filter((other) => other !== key)
      : [...now.keys, key]
    selected.value = keys.length > 0 ? { keys, dir: now.dir } : null
  }

  /** What a lasso or a brush stroke caught, in stroke order, no repeats. */
  function addSelected(keys: string[]): void {
    const now = selected.value
    const have = new Set(now?.keys ?? [])
    const fresh = keys.filter((key) => !have.has(key))
    if (fresh.length === 0) return
    selected.value = { keys: [...(now?.keys ?? []), ...fresh], dir: now?.dir ?? 'both' }
  }

  function setSelectedDir(dir: ScenarioDir): void {
    const now = selected.value
    if (!now || now.dir === dir) return
    selected.value = { keys: now.keys, dir }
  }

  function hover(ref_: StreetRef | null): void {
    const next = ref_ && ref_.keys.length > 0 ? ref_ : null
    if (sameRef(hovered.value, next)) return
    hovered.value = next
  }

  /** Put the streets of the loaded graph in, and fold what they teach us. */
  function setStreets(next: Map<string, Street>): void {
    streets.value = markRaw(next)
    normalizeOneWay()
  }

  /**
   * A one-way street can only be modified one way. An entry restored as 'fwd'
   * or 'bwd' on a street that has a single edge reads better as 'both'.
   */
  function normalizeOneWay(): void {
    if (streets.value.size === 0 || edgeModifications.value.size === 0) return
    let changed = false
    const next = new Map(edgeModifications.value)

    for (const [key, mod] of next) {
      if (mod.dir === 'both') continue
      const street = streets.value.get(key)
      if (street && street.oneway) {
        next.set(key, { ...mod, dir: 'both' })
        changed = true
      }
    }

    if (changed) edgeModifications.value = next
  }

  function restore(entries: Array<{ key: string; action: string; dir: string; name?: string }>) {
    const next = new Map<string, StreetMod>()
    for (const entry of entries) {
      if (!entry || typeof entry.key !== 'string') continue
      next.set(entry.key, {
        action: entry.action as ScenarioAction,
        dir: (entry.dir as ScenarioDir) || 'both',
        name: entry.name || ''
      })
    }
    edgeModifications.value = next
    normalizeOneWay()
  }

  /** What goes to localStorage. */
  function serialize() {
    return Array.from(edgeModifications.value.entries()).map(([key, mod]) => ({
      key,
      action: mod.action,
      dir: mod.dir,
      name: mod.name
    }))
  }

  return {
    // State
    edgeModifications,
    isOpen,
    activeTab,
    selected,
    hovered,
    mapMode,
    tool,
    brushRadius,
    streets,

    // Getters
    selectedSet,
    hoveredSet,
    count,
    hasModifications,
    signature,
    hash,
    list,
    wire,

    // Actions
    get,
    set,
    setMany,
    remove,
    removeMany,
    setDir,
    clear,
    select,
    toggleSelected,
    addSelected,
    setSelectedDir,
    hover,
    setStreets,
    normalizeOneWay,
    restore,
    serialize
  }
})
