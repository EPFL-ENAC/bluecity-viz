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

// The inputs of a traffic analysis. This is all we keep in an investigation and
// all we write to localStorage. Results are recomputed on demand.
export interface TrafficAnalysisInputs {
  isOpen: boolean
  edgeModifications: Array<{ u: number; v: number; action: string; name?: string }>
  activeVisualization: TrafficVisualization
  useCongestionModel: boolean
  congestionIterations: number
  elasticDemand: boolean
  filterBusRoutes: boolean
}

// The results of a run. Big (about 10k rows per array), kept in memory only.
export interface TrafficResults {
  nodePairs: Array<{ origin: number; destination: number }>
  originalEdgeUsage: EdgeUsageRow[]
  newEdgeUsage: EdgeUsageRow[]
  impactStatistics: any | null
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
