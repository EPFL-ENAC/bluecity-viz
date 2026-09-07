import type {
  Investigation,
  PersistedState,
  Project,
  TrafficAnalysisInputs,
  TrafficVisualization
} from './types'

const STORAGE_KEY = 'bluecity-layers-store'

// v1 stored the full traffic results (edge usage, node pairs) inside every
// investigation, which made the payload a few MB and blew the quota. v2 keeps
// only the inputs, the results are recomputed on demand.
export const SCHEMA_VERSION = 2

export function defaultTrafficInputs(): TrafficAnalysisInputs {
  return {
    isOpen: false,
    edgeModifications: [],
    activeVisualization: 'none',
    useCongestionModel: false,
    congestionIterations: 1,
    elasticDemand: false,
    filterBusRoutes: false
  }
}

// Keep the input fields only. Anything else (nodePairs, originalEdgeUsage,
// newEdgeUsage, impactStatistics) is dropped here.
function pickTrafficInputs(raw: any): TrafficAnalysisInputs {
  const defaults = defaultTrafficInputs()
  if (!raw || typeof raw !== 'object') return defaults

  return {
    isOpen: !!raw.isOpen,
    edgeModifications: Array.isArray(raw.edgeModifications)
      ? raw.edgeModifications
          .filter((mod: any) => mod && typeof mod === 'object')
          .map((mod: any) => ({
            u: Number(mod.u),
            v: Number(mod.v),
            action: String(mod.action ?? 'remove'),
            name: typeof mod.name === 'string' ? mod.name : undefined
          }))
      : [],
    activeVisualization: (raw.activeVisualization ?? 'none') as TrafficVisualization,
    useCongestionModel: !!raw.useCongestionModel,
    congestionIterations: Number(raw.congestionIterations) || 1,
    elasticDemand: !!raw.elasticDemand,
    filterBusRoutes: !!raw.filterBusRoutes
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
