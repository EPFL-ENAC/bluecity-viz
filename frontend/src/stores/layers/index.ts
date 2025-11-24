import { layerGroups as configLayerGroups } from '@/config/mapConfig'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

// Import modular functionality
import { createInvestigationManagement } from './investigationManagement'
import { createLayerManagement } from './layerManagement'
import { clearPersistedData, loadPersistedState, saveStateToStorage } from './persistence'
import { createSourceManagement } from './sourceManagement'
import type { PersistedState, Project, TrafficAnalysisState } from './types'
import { createUrlSharingComposable } from './urlSharing'

// Re-export types for backward compatibility
export type { Investigation, Project } from './types'

export const useLayersStore = defineStore('layers', () => {
  // Load persisted state
  const persistedState = loadPersistedState()

  // Core state
  const layerGroups = ref(configLayerGroups)
  const sp0Period = ref<string>(persistedState.sp0Period || '2020-2023')
  const selectedLayers = ref<string[]>(persistedState.selectedLayers || [])

  const availableResourceSources = ref<string[]>(
    persistedState.availableResourceSources || [
      'accessibility_atlas',
      'lausanne_migration',
      'lausanne_temperature'
    ]
  )

  const activeSources = ref<string[]>(
    persistedState.activeSources || ['lausanne_migration', 'lausanne_temperature']
  )

  const filteredCategories = ref<Record<string, Record<string, string[]>>>({})

  const expandedGroups = ref<Record<string, boolean>>(
    persistedState.expandedGroups ||
      Object.fromEntries(layerGroups.value.map((group: any) => [group.id, !!group.expanded]))
  )

  const projects = ref<Project[]>(
    persistedState.projects || [
      {
        id: 'project-1',
        name: 'Project 1',
        expanded: true,
        investigations: [
          {
            id: 'inv-1',
            name: 'Investigation 1',
            selectedSources: ['lausanne_migration'],
            selectedLayers: ['lausanne_pop_density-layer'],
            createdAt: new Date('2024-01-01')
          },
          {
            id: 'inv-2',
            name: 'Investigation 2',
            selectedSources: ['lausanne_temperature'],
            selectedLayers: ['lausanne_temperature-layer'],
            createdAt: new Date('2024-01-02')
          }
        ]
      },
      {
        id: 'project-2',
        name: 'Project 2',
        expanded: false,
        investigations: [
          {
            id: 'inv-3',
            name: 'Investigation 1',
            selectedSources: ['lausanne_aqi'],
            selectedLayers: ['lausanne_aqi'],
            createdAt: new Date('2024-01-03')
          }
        ]
      }
    ]
  )

  const activeInvestigationId = ref<string | null>(persistedState.activeInvestigationId || 'inv-1')

  // Traffic analysis state management functions
  function getTrafficAnalysisState(): TrafficAnalysisState {
    const trafficStore = useTrafficAnalysisStore()

    // Convert to plain objects to avoid storing reactive proxies
    return {
      isOpen: trafficStore.isOpen,
      removedEdges: JSON.parse(JSON.stringify(trafficStore.removedEdgesArray)),
      nodePairs: JSON.parse(JSON.stringify(trafficStore.nodePairs)),
      originalEdgeUsage: JSON.parse(JSON.stringify(trafficStore.originalEdgeUsage)),
      newEdgeUsage: JSON.parse(JSON.stringify(trafficStore.newEdgeUsage)),
      impactStatistics: trafficStore.impactStatistics
        ? JSON.parse(JSON.stringify(trafficStore.impactStatistics))
        : null,
      activeVisualization: trafficStore.activeVisualization
    }
  }

  function applyTrafficAnalysisState(state: TrafficAnalysisState): void {
    const trafficStore = useTrafficAnalysisStore()

    // Use batch restore to apply all changes at once (much faster)
    trafficStore.restoreState(state)
  }

  // Filter categories function
  function filterOutCategories(layerId: string, variable: string, categories: string[]) {
    filteredCategories.value[layerId][variable] = categories
  }

  // Create investigation management first (without dependencies)
  const investigationMgmt = createInvestigationManagement(
    projects,
    activeInvestigationId,
    availableResourceSources,
    selectedLayers,
    (sourceIds: string[]) => {
      availableResourceSources.value = [...sourceIds]
    },
    (sourceIds: string[]) => {
      activeSources.value = [...sourceIds]
    },
    (selection: string[] | null) => {
      if (selection !== null) {
        selectedLayers.value = [...selection]
      } else {
        selectedLayers.value.length = 0
      }
      investigationMgmt.updateCurrentInvestigation()
    },
    getTrafficAnalysisState,
    applyTrafficAnalysisState
  )

  // Create layer management
  const layerMgmt = createLayerManagement(
    selectedLayers,
    layerGroups,
    expandedGroups,
    investigationMgmt.updateCurrentInvestigation
  )

  // Create source management
  const sourceMgmt = createSourceManagement(
    availableResourceSources,
    activeSources,
    selectedLayers,
    layerMgmt.getLayersBySource,
    investigationMgmt.updateCurrentInvestigation
  )

  // Create URL sharing functionality
  const urlSharing = createUrlSharingComposable(
    investigationMgmt.activeInvestigation,
    sp0Period,
    projects,
    investigationMgmt.switchToInvestigation
  )

  // Initialize store
  function initializeInvestigations() {
    // Restore traffic panel state
    const trafficStore = useTrafficAnalysisStore()
    if (persistedState.trafficPanelOpen) {
      trafficStore.openPanel()
    }

    // First try to load state from URL
    const loadedFromUrl = urlSharing.loadStateFromUrl()

    // If no URL state was loaded, apply the default active investigation
    if (!loadedFromUrl && activeInvestigationId.value) {
      investigationMgmt.switchToInvestigation(activeInvestigationId.value)
    }
  }

  // Persist state to localStorage
  function persistState() {
    const trafficStore = useTrafficAnalysisStore()

    const stateToPersist: PersistedState = {
      selectedLayers: selectedLayers.value,
      availableResourceSources: availableResourceSources.value,
      activeSources: activeSources.value,
      projects: projects.value,
      activeInvestigationId: activeInvestigationId.value,
      sp0Period: sp0Period.value,
      expandedGroups: expandedGroups.value,
      trafficPanelOpen: trafficStore.isOpen
    }
    saveStateToStorage(stateToPersist)
  }

  // Set up watchers to automatically persist state changes
  watch(
    [
      selectedLayers,
      availableResourceSources,
      activeSources,
      projects,
      activeInvestigationId,
      sp0Period,
      expandedGroups
    ],
    () => {
      // Debounce the persistence to avoid too frequent writes
      if (!investigationMgmt.isLoadingInvestigation.value) {
        setTimeout(persistState, 100)
      }
    },
    { deep: true }
  )

  // Watch traffic store for changes to persist
  const trafficStore = useTrafficAnalysisStore()
  watch(
    () => ({
      isOpen: trafficStore.isOpen,
      removedEdgesSize: trafficStore.removedEdges.size,
      nodePairsLength: trafficStore.nodePairs.length,
      originalEdgeUsageLength: trafficStore.originalEdgeUsage.length,
      newEdgeUsageLength: trafficStore.newEdgeUsage.length,
      hasImpactStatistics: trafficStore.impactStatistics !== null,
      activeVisualization: trafficStore.activeVisualization
    }),
    () => {
      if (!investigationMgmt.isLoadingInvestigation.value) {
        investigationMgmt.updateCurrentInvestigation()
        setTimeout(persistState, 100)
      }
    }
  )

  return {
    // Core state
    layerGroups,
    sp0Period,
    selectedLayers,
    availableResourceSources,
    activeSources,
    filteredCategories,
    expandedGroups,
    projects,
    activeInvestigationId,

    // Computed from modules
    ...layerMgmt,
    ...sourceMgmt,

    // Investigation management
    activeInvestigation: investigationMgmt.activeInvestigation,
    toggleProject: investigationMgmt.toggleProject,
    findInvestigation: investigationMgmt.findInvestigation,
    switchToInvestigation: investigationMgmt.switchToInvestigation,
    saveCurrentState: investigationMgmt.saveCurrentState,
    createProject: investigationMgmt.createProject,
    removeProject: investigationMgmt.removeProject,
    removeInvestigation: investigationMgmt.removeInvestigation,

    // Utility functions
    filterOutCategories,
    initializeInvestigations,
    persistState,
    generateShareableUrl: urlSharing.generateShareableUrl,
    loadStateFromUrl: urlSharing.loadStateFromUrl,
    clearPersistedData
  }
})
