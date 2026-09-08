import { layerGroups as configLayerGroups } from '@/config/mapConfig'
import { areaKey } from '@/services/trafficAnalysis'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { defineStore } from 'pinia'
import { ref, shallowRef, toRaw, watch } from 'vue'

// Import modular functionality
import { createInvestigationManagement } from './investigationManagement'
import { createLayerManagement } from './layerManagement'
import {
  clearPersistedData,
  createPersistScheduler,
  loadPersistedState,
  saveStateToStorage
} from './persistence'
import { createSourceManagement } from './sourceManagement'
import { getResults, rememberResults } from './trafficResultsCache'
import type { PersistedState, Project, TrafficAnalysisInputs } from './types'
import { createUrlSharingComposable } from './urlSharing'

// Re-export types for backward compatibility
export type { Investigation, Project } from './types'

export const useLayersStore = defineStore('layers', () => {
  // Load persisted state
  const persistedState = loadPersistedState()

  // Core state. shallowRef: the layer config is a big static tree, we only ever
  // read it, so there is no point making all of it reactive.
  const layerGroups = shallowRef(configLayerGroups)
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

  // Deep on purpose: LegendMap and MapLibreMap mutate this in place.
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

  // Only the inputs. No clone of the result arrays, this runs on every layer
  // toggle and every edge click.
  function getTrafficAnalysisInputs(): TrafficAnalysisInputs {
    const trafficStore = useTrafficAnalysisStore()

    const edgeModificationsArray = Array.from(trafficStore.edgeModifications.entries()).map(
      ([key, value]) => {
        const [u, v] = key.split('-').map(Number)
        return { u, v, action: value.action, name: value.name }
      }
    )

    return {
      isOpen: trafficStore.isOpen,
      edgeModifications: edgeModificationsArray,
      activeVisualization: trafficStore.activeVisualization,
      useCongestionModel: trafficStore.useCongestionModel,
      congestionIterations: trafficStore.congestionIterations,
      elasticDemand: trafficStore.elasticDemand,
      filterBusRoutes: trafficStore.filterBusRoutes,
      odPairs: trafficStore.odPairs,
      area: trafficStore.area ? { ...trafficStore.area } : null
    }
  }

  // Restore the inputs, plus the results we still have in memory for that
  // investigation. The arrays are always passed, empty when we have nothing.
  function applyTrafficAnalysisState(inputs: TrafficAnalysisInputs, investigationId: string): void {
    const trafficStore = useTrafficAnalysisStore()
    const area = inputs.area ?? null
    // Results of another area mean nothing here: the edge ids are not the same
    // graph. Drop them and keep the inputs.
    const saved = getResults(investigationId)
    const results = saved && saved.resultAreaKey === areaKey(area) ? saved : null

    trafficStore.restoreState({
      isOpen: inputs.isOpen,
      edgeModifications: inputs.edgeModifications ?? [],
      nodePairs: results?.nodePairs ?? [],
      originalEdgeUsage: results?.originalEdgeUsage ?? [],
      newEdgeUsage: results?.newEdgeUsage ?? [],
      impactStatistics: results?.impactStatistics ?? null,
      activeVisualization: inputs.activeVisualization ?? 'none',
      // an input, restoreState assigns it without clearing the results above
      odPairs: inputs.odPairs ?? null,
      resultOdPairs: results?.resultOdPairs ?? null,
      area
    })

    // The other routing options are not part of restoreState's own defaults,
    // set them here so an investigation without them falls back to off.
    trafficStore.useCongestionModel = inputs.useCongestionModel ?? false
    trafficStore.congestionIterations = inputs.congestionIterations ?? 1
    trafficStore.elasticDemand = inputs.elasticDemand ?? false
    trafficStore.filterBusRoutes = inputs.filterBusRoutes ?? false
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
      selectedLayers.value = selection !== null ? [...selection] : []
      investigationMgmt.updateCurrentInvestigation()
    },
    getTrafficAnalysisInputs,
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

  const persist = createPersistScheduler(persistState, 300)

  function schedulePersist() {
    if (!investigationMgmt.isLoadingInvestigation.value) {
      persist.schedule()
    }
  }

  // Set up watchers to automatically persist state changes.
  // No deep here: these refs are always replaced, never mutated in place.
  watch(
    [selectedLayers, availableResourceSources, activeSources, activeInvestigationId, sp0Period],
    schedulePersist
  )

  // These two are mutated in place (rename, toggleProject, toggleGroup,
  // updateCurrentInvestigation), so they need deep. Both stay small now that
  // the results are out of the investigations.
  watch([projects, expandedGroups], schedulePersist, { deep: true })

  // Watch traffic store for changes to persist. An array of sources, compared
  // one by one: no new object on every run. edgeModifications (a Map) and
  // newEdgeUsage (a shallowRef array) are replaced by the store on each change,
  // so comparing them by identity is enough.
  const trafficStore = useTrafficAnalysisStore()
  watch(
    [
      () => trafficStore.isOpen,
      () => trafficStore.edgeModifications,
      () => trafficStore.activeVisualization,
      () => trafficStore.useCongestionModel,
      () => trafficStore.congestionIterations,
      () => trafficStore.elasticDemand,
      () => trafficStore.filterBusRoutes,
      () => trafficStore.odPairs,
      () => trafficStore.area,
      () => trafficStore.newEdgeUsage
    ],
    () => {
      if (investigationMgmt.isLoadingInvestigation.value) return

      investigationMgmt.updateCurrentInvestigation()

      // Results stay in memory, keyed by investigation.
      rememberResults(activeInvestigationId.value, {
        nodePairs: toRaw(trafficStore.nodePairs),
        originalEdgeUsage: toRaw(trafficStore.originalEdgeUsage),
        newEdgeUsage: toRaw(trafficStore.newEdgeUsage),
        impactStatistics: toRaw(trafficStore.impactStatistics),
        resultOdPairs: trafficStore.resultOdPairs,
        resultAreaKey: areaKey(trafficStore.area)
      })

      persist.schedule()
    }
  )

  // Do not lose a pending write when the tab goes away.
  if (typeof window !== 'undefined') {
    window.addEventListener('pagehide', persist.flush)
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') persist.flush()
    })
  }

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
    flushPersistState: persist.flush,
    generateShareableUrl: urlSharing.generateShareableUrl,
    loadStateFromUrl: urlSharing.loadStateFromUrl,
    clearPersistedData
  }
})
