import type {
  Investigation,
  PersistedState,
  Project,
  ScenarioInputs,
  ScenarioModEntry,
  TrafficAnalysisInputs,
  TrafficAreaSelection,
  TrafficVisualization
} from './types'

const STORAGE_KEY = 'bluecity-layers-store'

// v1 stored the full traffic results (edge usage, node pairs) inside every
// investigation, which made the payload a few MB and blew the quota. v2 keeps
// only the inputs, the results are recomputed on demand. v3 adds the OD pair
// count (odPairs), missing in older entries and read back as null. v5 moves the
// edge modifications out of the traffic tool into a scenario both tools share,
// keyed by street instead of by directed edge, and adds the area the scenario
// runs on, missing in older entries and read back as null, the default city.
export const SCHEMA_VERSION = 5

// The area must sit inside the country and stay in the range the backend
// accepts, else the first Calculate would fail on a saved circle.
const SWISS_BOUNDS = { minLon: 5.8, minLat: 45.7, maxLon: 10.6, maxLat: 47.9 }
const RADIUS_M = { min: 500, max: 10_000 }
// The dock is 340 px wide, a longer name would only be cut on screen.
const MAX_AREA_NAME = 60

/** A saved circle, or null when it is missing or out of range. */
export function pickArea(raw: any): TrafficAreaSelection | null {
  if (!raw || typeof raw !== 'object' || raw.kind !== 'circle') return null
  const lon = Number(raw.lon)
  const lat = Number(raw.lat)
  const radiusM = Number(raw.radiusM)
  if (!Number.isFinite(lon) || !Number.isFinite(lat) || !Number.isFinite(radiusM)) return null
  if (lon < SWISS_BOUNDS.minLon || lon > SWISS_BOUNDS.maxLon) return null
  if (lat < SWISS_BOUNDS.minLat || lat > SWISS_BOUNDS.maxLat) return null
  if (radiusM < RADIUS_M.min || radiusM > RADIUS_M.max) return null
  const area: TrafficAreaSelection = { kind: 'circle', lon, lat, radiusM }
  // The name is a label written by the picker. An area saved before v5.1 has
  // none, and the dock falls back to the coordinates.
  const name = typeof raw.name === 'string' ? raw.name.trim().slice(0, MAX_AREA_NAME) : ''
  if (name) area.name = name
  return area
}

export function defaultTrafficInputs(): TrafficAnalysisInputs {
  return {
    isOpen: false,
    activeVisualization: 'none',
    useCongestionModel: false,
    congestionIterations: 1,
    elasticDemand: false,
    filterBusRoutes: false,
    odPairs: null,
    area: null
  }
}

// v3 wrote one row per directed edge, with speed50 style actions. The scenario
// keys a street once and says which way it is modified, so the two rows of a
// two-way street fold into a single "both" entry.
const ACTION_V3_TO_V4: Record<string, string> = {
  remove: 'remove',
  speed50: '50',
  speed30: '30',
  speed10: '10'
}

export function migrateDirectedMods(raw: any): ScenarioModEntry[] {
  if (!Array.isArray(raw)) return []

  const byStreet = new Map<string, ScenarioModEntry>()

  for (const mod of raw) {
    if (!mod || typeof mod !== 'object') continue
    const u = Number(mod.u)
    const v = Number(mod.v)
    if (!Number.isFinite(u) || !Number.isFinite(v)) continue

    const key = u <= v ? `${u}-${v}` : `${v}-${u}`
    const dir = u <= v ? 'fwd' : 'bwd'
    const action = ACTION_V3_TO_V4[String(mod.action)] ?? 'remove'
    const name = typeof mod.name === 'string' ? mod.name : undefined

    const seen = byStreet.get(key)
    if (!seen) {
      byStreet.set(key, { key, action, dir, name })
    } else if (seen.dir !== dir && seen.dir !== 'both') {
      // the other direction of the same street: one entry, both ways.
      // The first action wins, they were always written as a pair.
      byStreet.set(key, { ...seen, dir: 'both', name: seen.name ?? name })
    }
  }

  return Array.from(byStreet.values())
}

export function defaultScenarioInputs(): ScenarioInputs {
  return { edgeModifications: [] }
}

export function pickScenarioInputs(raw: any, legacyTraffic: any): ScenarioInputs {
  // v4 and later keep their own block; older entries carry the modifications
  // inside the traffic tool.
  if (raw && typeof raw === 'object' && Array.isArray(raw.edgeModifications)) {
    return {
      edgeModifications: raw.edgeModifications
        .filter((mod: any) => mod && typeof mod === 'object' && typeof mod.key === 'string')
        .map((mod: any) => ({
          key: String(mod.key),
          action: String(mod.action ?? 'remove'),
          dir: String(mod.dir ?? 'both'),
          name: typeof mod.name === 'string' ? mod.name : undefined,
          group: typeof mod.group === 'string' && mod.group ? mod.group : undefined
        }))
    }
  }

  return { edgeModifications: migrateDirectedMods(legacyTraffic?.edgeModifications) }
}

// Keep the input fields only. Anything else (nodePairs, originalEdgeUsage,
// newEdgeUsage, impactStatistics) is dropped here.
export function pickTrafficInputs(raw: any): TrafficAnalysisInputs {
  const defaults = defaultTrafficInputs()
  if (!raw || typeof raw !== 'object') return defaults

  return {
    isOpen: !!raw.isOpen,
    activeVisualization: (raw.activeVisualization ?? 'none') as TrafficVisualization,
    useCongestionModel: !!raw.useCongestionModel,
    congestionIterations: Number(raw.congestionIterations) || 1,
    elasticDemand: !!raw.elasticDemand,
    filterBusRoutes: !!raw.filterBusRoutes,
    // missing (v2 and older) or broken reads back as null, the server default
    odPairs: Number.isInteger(raw.odPairs) && raw.odPairs > 0 ? raw.odPairs : null,
    // missing (v3 and older) or broken reads back as null, the default city
    area: pickArea(raw.area)
  }
}

// Runs on every load, v1 or v2, so a stray bulk field is always stripped.
// It must never throw on an old or broken shape.
export function migratePersistedState(raw: unknown): Partial<PersistedState> {
  if (!raw || typeof raw !== 'object') return {}

  const source = raw as Record<string, any>
  const state: Partial<PersistedState> = { ...source }

  if (Array.isArray(source.projects)) {
    state.projects = source.projects
      .filter((project: any) => project && typeof project === 'object')
      .map((project: any): Project => {
        const investigations = Array.isArray(project.investigations) ? project.investigations : []
        return {
          ...project,
          investigations: investigations
            .filter((inv: any) => inv && typeof inv === 'object')
            .map((inv: any): Investigation => {
              const migrated: Investigation = {
                id: String(inv.id),
                name: String(inv.name ?? 'Investigation'),
                selectedSources: Array.isArray(inv.selectedSources) ? inv.selectedSources : [],
                selectedLayers: Array.isArray(inv.selectedLayers) ? inv.selectedLayers : [],
                createdAt: inv.createdAt ? new Date(inv.createdAt) : new Date()
              }
              if (inv.trafficAnalysis) {
                migrated.trafficAnalysis = pickTrafficInputs(inv.trafficAnalysis)
              }
              const scenario = pickScenarioInputs(inv.scenario, inv.trafficAnalysis)
              if (scenario.edgeModifications.length > 0 || inv.scenario) {
                migrated.scenario = scenario
              }
              return migrated
            })
        }
      })
  } else {
    delete state.projects
  }

  state.version = SCHEMA_VERSION
  return state
}

export function loadPersistedState(): Partial<PersistedState> {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      return migratePersistedState(JSON.parse(stored))
    }
  } catch (error) {
    console.warn('Failed to load persisted state:', error)
  }
  return {}
}

export function saveStateToStorage(state: PersistedState) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...state, version: SCHEMA_VERSION }))
  } catch (error) {
    console.warn('Failed to save state to storage:', error)
  }
}

export function clearPersistedData() {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch (error) {
    console.warn('Failed to clear persisted data:', error)
  }
}

// One trailing debounce: a single timer handle, cleared and re-armed on each
// schedule() call. N mutations in a row means one write, not N.
export function createPersistScheduler(save: () => void, delay = 300) {
  let handle: ReturnType<typeof setTimeout> | null = null

  function cancel() {
    if (handle !== null) {
      clearTimeout(handle)
      handle = null
    }
  }

  function schedule() {
    cancel()
    handle = setTimeout(() => {
      handle = null
      save()
    }, delay)
  }

  // Write now, but only if a write is pending.
  function flush() {
    if (handle !== null) {
      cancel()
      save()
    }
  }

  return { schedule, flush, cancel }
}
