// Traffic analysis state for an investigation
export interface TrafficAnalysisState {
  isOpen: boolean
  edgeModifications: Array<{ u: number; v: number; action: string; name?: string }>
  nodePairs: Array<{ origin: number; destination: number }>
  originalEdgeUsage: Array<{
    u: number
    v: number
    count: number
    frequency: number
    delta_count?: number
    co2_per_use?: number
  }>
  newEdgeUsage: Array<{
    u: number
    v: number
    count: number
    frequency: number
    delta_count?: number
    co2_per_use?: number
  }>
  impactStatistics: any | null
  activeVisualization: 'none' | 'frequency' | 'delta' | 'co2' | 'co2_delta' | 'routes'
}

// Investigation interface
export interface Investigation {
  id: string
  name: string
  selectedSources: string[]
  selectedLayers: string[]
  createdAt: Date
  trafficAnalysis?: TrafficAnalysisState
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
  selectedLayers: string[]
  availableResourceSources: string[]
  activeSources: string[]
  projects: Project[]
  activeInvestigationId: string | null
  sp0Period: string
  expandedGroups: Record<string, boolean>
  trafficPanelOpen: boolean
}
