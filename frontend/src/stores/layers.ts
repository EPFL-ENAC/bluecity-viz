import type { CustomSourceSpecification } from '@/config/layerTypes'
import { layerGroups as configLayerGroups, mapConfig } from '@/config/mapConfig'
import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'

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

// Persistence helpers
const STORAGE_KEY = 'bluecity-layers-store'

interface PersistedState {
  selectedLayers: string[]
  availableResourceSources: string[]
  activeSources: string[]
  projects: Project[]
  activeInvestigationId: string | null
  sp0Period: string
  expandedGroups: Record<string, boolean>
}

function loadPersistedState(): Partial<PersistedState> {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      const parsed = JSON.parse(stored)
      // Convert date strings back to Date objects for investigations
      if (parsed.projects) {
        parsed.projects.forEach((project: Project) => {
          project.investigations.forEach((investigation: Investigation) => {
            investigation.createdAt = new Date(investigation.createdAt)
          })
        })
      }
      return parsed
    }
  } catch (error) {
    console.warn('Failed to load persisted state:', error)
  }
  return {}
}

function saveStateToStorage(state: PersistedState) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch (error) {
    console.warn('Failed to save state to storage:', error)
  }
}

export const useLayersStore = defineStore('layers', () => {
  // Load persisted state
  const persistedState = loadPersistedState()

  // Store the layer groups from config
  const layerGroups = ref<
    {
      id: string
      label: string
      expanded: boolean
      multiple: boolean
      layers: any[]
    }[]
  >(configLayerGroups)

  const sp0Period = ref<string>(persistedState.sp0Period || '2020-2023')

  // Selected layer IDs
  const selectedLayers = ref<string[]>(persistedState.selectedLayers || [])

  // Available source IDs in the resources panel (sources user has added)
  const availableResourceSources = ref<string[]>(
    persistedState.availableResourceSources || [
      'accessibility_atlas',
      'lausanne_migration',
      'lausanne_temperature'
    ]
  )

  // Active/selected source IDs (sources that are currently enabled)
  const activeSources = ref<string[]>(
    persistedState.activeSources || ['lausanne_migration', 'lausanne_temperature']
  )

  // Store the filtered categories for each layer
  const filteredCategories = ref<Record<string, Record<string, string[]>>>({})

  function filterOutCategories(layerId: string, variable: string, categories: string[]) {
    filteredCategories.value[layerId][variable] = categories
  }

  // Expanded state for each group
  const expandedGroups = ref<Record<string, boolean>>(
    persistedState.expandedGroups ||
      Object.fromEntries(layerGroups.value.map((group) => [group.id, !!group.expanded]))
  )

  // Flatten all layers for internal use
  const possibleLayers = computed(() => {
    return layerGroups.value.flatMap((group) =>
      group.layers.map((layer) => ({
        id: layer.layer.id, // Extract the layer ID correctly
        label: layer.label,
        info: layer.info,
        attribution: layer.source.attribution,
        groupId: group.id
      }))
    )
  })

  // Get visible layer configurations
  const visibleLayers = computed(() => {
    return mapConfig.layers.filter((layer) => selectedLayers.value.includes(layer.layer.id))
  })

  // Get list of all available sources
  const availableSources = computed((): CustomSourceSpecification[] => {
    return mapConfig.sources
  })

  // Get layers that use a specific source
  function getLayersBySource(sourceId: string) {
    return mapConfig.layers.filter((layer) => {
      // Check if the layer's source ID matches the provided source ID
      const source = layer.source as CustomSourceSpecification
      return source.id === sourceId
    })
  }

  // Get all layers grouped by their source
  const layersBySource = computed(() => {
    const sourceMap = new Map<string, typeof mapConfig.layers>()

    mapConfig.layers.forEach((layer) => {
      const source = layer.source as CustomSourceSpecification
      const sourceId = source.id
      if (sourceId) {
        if (!sourceMap.has(sourceId)) {
          sourceMap.set(sourceId, [])
        }
        sourceMap.get(sourceId)!.push(layer)
      }
    })

    return sourceMap
  })

  // Toggle group expansion
  function toggleGroup(groupId: string) {
    expandedGroups.value[groupId] = !expandedGroups.value[groupId]
    const group = layerGroups.value.find((group) => group.id === groupId)
    if (group) group.expanded = expandedGroups.value[groupId]
  }

  // Check if any layer in a group is selected
  function isGroupVisible(groupId: string): boolean {
    return selectedLayers.value.some((id) => {
      const layer = possibleLayers.value.find((l) => l.id === id)
      return layer && layer.groupId === groupId
    })
  }

  // Toggle visibility of all layers in a group
  function toggleGroupVisibility(groupId: string) {
    const groupLayers = possibleLayers.value.filter((layer) => layer.groupId === groupId)
    const groupLayerIds = groupLayers.map((layer) => layer.id)

    // Check if any layer from this group is currently selected
    const isVisible = isGroupVisible(groupId)

    if (isVisible) {
      // If visible, remove all layers from this group
      selectedLayers.value = selectedLayers.value.filter((id) => !groupLayerIds.includes(id))
    } else {
      // If not visible, add layers according to group's selection mode
      const group = layerGroups.value.find((g) => g.id === groupId)
      if (group?.multiple) {
        // For multiple selection groups, add all layers
        selectedLayers.value = [...selectedLayers.value, ...groupLayerIds]
      } else if (groupLayers.length > 0) {
        // For single selection groups, add only the first layer
        const otherGroupLayers = selectedLayers.value.filter((id) => {
          const layer = possibleLayers.value.find((l) => l.id === id)
          return layer && layer.groupId !== groupId
        })
        selectedLayers.value = [...otherGroupLayers, groupLayerIds[0]]
      }
    }
    // Update active investigation if one exists
    updateCurrentInvestigation()
  }

  // Update selected layers (for checkboxes/multiple selection)
  function updateSelectedLayers(newSelection: string[] | null) {
    if (newSelection !== null) {
      selectedLayers.value = [...newSelection]
    } else {
      selectedLayers.value.length = 0
    }
    // Update active investigation if one exists
    updateCurrentInvestigation()
  }

  // Update single layer selection (for radio buttons/single selection)
  function updateSingleLayerSelection(groupId: string, layerId: string) {
    // Create a new array without any layers from this group
    const otherGroupLayers = selectedLayers.value.filter((id) => {
      const layer = possibleLayers.value.find((l) => l.id === id)
      return layer && layer.groupId !== groupId
    })

    // Add the selected layer and update the array
    updateSelectedLayers([...otherGroupLayers, layerId])
  }

  // Source management functions

  // Get available resource source objects (sources added to resources panel)
  const availableResourceSourceObjects = computed(() => {
    return mapConfig.sources.filter((source) => availableResourceSources.value.includes(source.id))
  })

  // Get sources that can be added to resources (not already added)
  const availableSourcesForDialog = computed(() => {
    return mapConfig.sources.filter((source) => !availableResourceSources.value.includes(source.id))
  })

  // Add sources to resources panel
  function addSources(sourceIds: string[]) {
    availableResourceSources.value = [...availableResourceSources.value, ...sourceIds]
    // Update active investigation if one exists
    updateCurrentInvestigation()
  }

  // Remove a source from resources panel
  function removeSource(sourceId: string) {
    availableResourceSources.value = availableResourceSources.value.filter(
      (id: string) => id !== sourceId
    )
    // Also remove from active sources and any layers from this source
    activeSources.value = activeSources.value.filter((id: string) => id !== sourceId)
    const layersFromSource = getLayersBySource(sourceId)
    const layerIds = layersFromSource.map((layer) => layer.layer.id)
    selectedLayers.value = selectedLayers.value.filter((id) => !layerIds.includes(id))
    // Update active investigation if one exists
    updateCurrentInvestigation()
  }

  // Toggle source active state (this will later be used for layer selection instead of automatic layer enabling)
  function toggleSource(sourceId: string, enabled: boolean | null) {
    if (enabled === null) return

    if (enabled) {
      // Add to active sources
      if (!activeSources.value.includes(sourceId)) {
        activeSources.value = [...activeSources.value, sourceId]
      }
    } else {
      // Remove from active sources
      activeSources.value = activeSources.value.filter((id: string) => id !== sourceId)
      // For now, also remove all layers from this source (this will change when layer selection is implemented)
      const layersFromSource = getLayersBySource(sourceId)
      const layerIds = layersFromSource.map((layer) => layer.layer.id)
      selectedLayers.value = selectedLayers.value.filter((id) => !layerIds.includes(id))
    }
    // Update active investigation if one exists
    updateCurrentInvestigation()
  }

  // Check if source is currently active
  function isSourceEnabled(sourceId: string): boolean {
    return activeSources.value.includes(sourceId)
  }

  // Update available resource sources (for investigations)
  function updateAvailableResourceSources(sourceIds: string[]) {
    availableResourceSources.value = [...sourceIds]
  }

  // Update active sources (for investigations)
  function updateActiveSources(sourceIds: string[]) {
    activeSources.value = [...sourceIds]
  }

  // Update current investigation with current state
  function updateCurrentInvestigation() {
    // Don't update if we're currently loading an investigation
    if (isLoadingInvestigation.value) return
    if (!activeInvestigationId.value) return

    const investigation = findInvestigation(activeInvestigationId.value)
    if (!investigation) return

    // Update the investigation with current state
    investigation.selectedSources = [...availableResourceSources.value]
    investigation.selectedLayers = [...selectedLayers.value]
  }

  // Investigation and Project Management

  // Projects with investigations
  const projects = ref<Project[]>(
    persistedState.projects || [
      {
        id: 'project-1',
        name: 'Urban Mobility Analysis',
        expanded: true,
        investigations: [
          {
            id: 'inv-1',
            name: 'Population Distribution',
            selectedSources: ['lausanne_migration'],
            selectedLayers: ['lausanne_pop_density-layer'],
            createdAt: new Date('2024-01-01')
          },
          {
            id: 'inv-2',
            name: 'Temperature Analysis',
            selectedSources: ['lausanne_temperature'],
            selectedLayers: ['lausanne_temperature-layer'],
            createdAt: new Date('2024-01-02')
          }
        ]
      },
      {
        id: 'project-2',
        name: 'Environmental Impact',
        expanded: false,
        investigations: [
          {
            id: 'inv-3',
            name: 'Air Quality Study',
            selectedSources: ['lausanne_aqi'],
            selectedLayers: ['lausanne_aqi'],
            createdAt: new Date('2024-01-03')
          }
        ]
      }
    ]
  )

  const activeInvestigationId = ref<string | null>(persistedState.activeInvestigationId || 'inv-1')

  // Computed active investigation
  const activeInvestigation = computed(() => {
    for (const project of projects.value) {
      const investigation = project.investigations.find(
        (inv) => inv.id === activeInvestigationId.value
      )
      if (investigation) return investigation
    }
    return null
  })

  // Toggle project expansion
  function toggleProject(projectId: string) {
    const project = projects.value.find((p) => p.id === projectId)
    if (project) {
      project.expanded = !project.expanded
    }
  }

  // Find investigation by ID
  function findInvestigation(id: string): Investigation | null {
    for (const project of projects.value) {
      const investigation = project.investigations.find((inv) => inv.id === id)
      if (investigation) return investigation
    }
    return null
  }

  // Track if we're currently loading an investigation to prevent auto-updates
  const isLoadingInvestigation = ref(false)

  // Switch to investigation
  function switchToInvestigation(investigationId: string | null) {
    if (!investigationId) return

    const investigation = findInvestigation(investigationId)
    if (!investigation) return

    // Set loading flag to prevent auto-updates during state restoration
    isLoadingInvestigation.value = true
    activeInvestigationId.value = investigationId

    // Apply investigation state to the store
    updateAvailableResourceSources(investigation.selectedSources)
    updateActiveSources(investigation.selectedSources)
    updateSelectedLayers(investigation.selectedLayers)

    // Clear loading flag
    isLoadingInvestigation.value = false
  }

  // Save current state as new investigation
  function saveCurrentState(projectId: string) {
    const project = projects.value.find((p) => p.id === projectId)
    if (!project) return

    const newInvestigation: Investigation = {
      id: `inv-${Date.now()}`,
      name: `Investigation ${project.investigations.length + 1}`,
      selectedSources: [...availableResourceSources.value],
      selectedLayers: [...selectedLayers.value],
      createdAt: new Date()
    }

    project.investigations.push(newInvestigation)
    activeInvestigationId.value = newInvestigation.id
  }

  // Remove investigation
  function removeInvestigation(investigationId: string) {
    for (const project of projects.value) {
      const index = project.investigations.findIndex((inv) => inv.id === investigationId)
      if (index !== -1) {
        project.investigations.splice(index, 1)

        // If removing active investigation, switch to first available
        if (activeInvestigationId.value === investigationId) {
          const firstInvestigation = projects.value.flatMap((p) => p.investigations)[0]
          if (firstInvestigation) {
            switchToInvestigation(firstInvestigation.id)
          } else {
            activeInvestigationId.value = null
          }
        }
        break
      }
    }
  }

  // Initialize store - apply initial investigation if available
  function initializeInvestigations() {
    if (activeInvestigationId.value) {
      switchToInvestigation(activeInvestigationId.value)
    }
  }

  // Persist state to localStorage
  function persistState() {
    const stateToPersist: PersistedState = {
      selectedLayers: selectedLayers.value,
      availableResourceSources: availableResourceSources.value,
      activeSources: activeSources.value,
      projects: projects.value,
      activeInvestigationId: activeInvestigationId.value,
      sp0Period: sp0Period.value,
      expandedGroups: expandedGroups.value
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
      if (!isLoadingInvestigation.value) {
        setTimeout(persistState, 100)
      }
    },
    { deep: true }
  )

  return {
    layerGroups,
    sp0Period,
    selectedLayers,
    availableResourceSources,
    activeSources,
    filteredCategories,
    expandedGroups,
    possibleLayers,
    visibleLayers,
    availableSources,
    layersBySource,
    availableResourceSourceObjects,
    availableSourcesForDialog,
    toggleGroup,
    isGroupVisible,
    filterOutCategories,
    toggleGroupVisibility,
    updateSelectedLayers,
    updateSingleLayerSelection,
    getLayersBySource,
    addSources,
    removeSource,
    toggleSource,
    isSourceEnabled,
    updateAvailableResourceSources,
    updateActiveSources,
    // Investigation management
    projects,
    activeInvestigationId,
    activeInvestigation,
    toggleProject,
    findInvestigation,
    switchToInvestigation,
    saveCurrentState,
    removeInvestigation,
    initializeInvestigations,
    persistState,
    // Utility function to clear persisted data (useful for debugging/reset)
    clearPersistedData: () => {
      try {
        localStorage.removeItem(STORAGE_KEY)
      } catch (error) {
        console.warn('Failed to clear persisted data:', error)
      }
    }
  }
})
