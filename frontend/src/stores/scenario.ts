import type { EdgeModification } from '@/services/trafficAnalysis'
import { scenarioHash, scenarioSignature } from '@/utils/scenarioHash'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

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
}

export interface EdgeRef {
  key: string
  dir: ScenarioDir
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

  /** clicking an edge opens the popover instead of cycling */
  const editMode = ref(false)
  const selected = ref<EdgeRef | null>(null)
  /** shared by the dock rows and the map, so hovering one lights the other */
  const hovered = ref<EdgeRef | null>(null)
  const mapMode = ref<'scenario' | 'result'>('scenario')

  /** The streets of the loaded graph, filled by useGraphEdges. */
  const streets = ref<Map<string, Street>>(new Map())

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

  function setDir(key: string, dir: ScenarioDir): void {
    const mod = edgeModifications.value.get(key)
    if (!mod) return
    set(key, { ...mod, dir })
  }

  function clear(): void {
    if (edgeModifications.value.size === 0) return
    edgeModifications.value = new Map()
  }

  function select(ref_: EdgeRef | null): void {
    selected.value = ref_
  }

  function hover(ref_: EdgeRef | null): void {
    const now = hovered.value
    if (now === ref_) return
    if (now && ref_ && now.key === ref_.key && now.dir === ref_.dir) return
    hovered.value = ref_
  }

  function setEditMode(on: boolean): void {
    editMode.value = on
    if (!on) selected.value = null
  }

  /** Put the streets of the loaded graph in, and fold what they teach us. */
  function setStreets(next: Map<string, Street>): void {
    streets.value = next
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
    editMode,
    selected,
    hovered,
    mapMode,
    streets,

    // Getters
    count,
    hasModifications,
    signature,
    hash,
    list,
    wire,

    // Actions
    get,
    set,
    remove,
    setDir,
    clear,
    select,
    hover,
    setEditMode,
    setStreets,
    normalizeOneWay,
    restore,
    serialize
  }
})
