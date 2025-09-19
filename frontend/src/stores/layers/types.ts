// Investigation interface
export interface Investigation {
  id: string
  name: string
  selectedSources: string[]
  selectedLayers: string[]
  createdAt: Date
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
}
