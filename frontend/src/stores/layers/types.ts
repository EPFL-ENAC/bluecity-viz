// One row of edge usage stats, same shape as EdgeUsageStats in the traffic store.
export interface EdgeUsageRow {
  u: number
  v: number
  count: number
  frequency: number
  delta_count?: number
  delta_frequency?: number
  co2_per_km?: number
  betweenness_centrality?: number
  delta_betweenness?: number
}

export type TrafficVisualization =
  | 'none'
  | 'frequency'
  | 'delta'
  | 'delta_relative'
  | 'co2'
  | 'co2_delta'
  | 'betweenness'
  | 'betweenness_delta'

// One modified street: both directed edges of `key`, or one of them.
export interface ScenarioModEntry {
  key: string
  action: string
  dir: string
  name?: string
}

// The modified graph. Shared by every tool, so it sits beside the tool inputs
// rather than inside them.
export interface ScenarioInputs {
  edgeModifications: ScenarioModEntry[]
}

// The inputs of a traffic analysis. This is all we keep in an investigation and
// all we write to localStorage. Results are recomputed on demand.
export interface TrafficAnalysisInputs {
  isOpen: boolean
  activeVisualization: TrafficVisualization
  useCongestionModel: boolean
  congestionIterations: number
  elasticDemand: boolean
  filterBusRoutes: boolean
  /** how many OD pairs to route, null for the server default */
  odPairs: number | null
  /** the area the scenario runs on, null for the default city */
  area: TrafficAreaSelection | null
}

// A circle on the map, the only shape the picker draws today.
export interface TrafficAreaSelection {
  kind: 'circle'
  lon: number
  lat: number
  radiusM: number
}

// The results of a run. Big (about 10k rows per array), kept in memory only.
export interface TrafficResults {
  nodePairs: Array<{ origin: number; destination: number }>
  originalEdgeUsage: EdgeUsageRow[]
  newEdgeUsage: EdgeUsageRow[]
  impactStatistics: any | null
  /** the OD pair count these results were computed with */
  resultOdPairs: number | null
  /** the area these results were computed on, so we never show them on another */
  resultAreaKey: string | null
  /** the scenario these results were computed on, to tell when they go stale */
  resultScenarioHash?: string | null
}

// Full state handed to trafficStore.restoreState(). The arrays are always
// present (empty when we have no results), the store reads them directly.
export interface TrafficAnalysisState extends TrafficAnalysisInputs, TrafficResults {}

// Investigation interface
export interface Investigation {
  id: string
  name: string
  selectedSources: string[]
  selectedLayers: string[]
  createdAt: Date
  trafficAnalysis?: TrafficAnalysisInputs
  scenario?: ScenarioInputs
}

// Project interface
export interface Project {
  id: string
  name: string
  expanded: boolean
  investigations: Investigation[]
}

// Persistence interface
export interface PersistedState {
  version?: number
  selectedLayers: string[]
  availableResourceSources: string[]
  activeSources: string[]
  projects: Project[]
  activeInvestigationId: string | null
  sp0Period: string
  expandedGroups: Record<string, boolean>
  trafficPanelOpen: boolean
}
