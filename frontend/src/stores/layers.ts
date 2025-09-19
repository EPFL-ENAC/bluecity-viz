import type { CustomSourceSpecification } from '@/config/layerTypes'
import { layerGroups as configLayerGroups, mapConfig } from '@/config/mapConfig'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export const useLayersStore = defineStore('layers', () => {
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

  const sp0Period = ref<string>('2020-2023')

  // Selected layer IDs
  const selectedLayers = ref<string[]>([])

  // Available source IDs in the resources panel (sources user has added)
  const availableResourceSources = ref<string[]>([
    'accessibility_atlas',
    'lausanne_migration',
    'lausanne_temperature'
  ])

  // Active/selected source IDs (sources that are currently enabled)
  const activeSources = ref<string[]>(['lausanne_migration', 'lausanne_temperature'])

  // Store the filtered categories for each layer
  const filteredCategories = ref<Record<string, Record<string, string[]>>>({})

  function filterOutCategories(layerId: string, variable: string, categories: string[]) {
    filteredCategories.value[layerId][variable] = categories
  }

  // Expanded state for each group
  const expandedGroups = ref<Record<string, boolean>>(
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
  }

  // Update selected layers (for checkboxes/multiple selection)
  function updateSelectedLayers(newSelection: string[] | null) {
    if (newSelection !== null) {
      selectedLayers.value = [...newSelection] // Use spread to ensure reactivity
    } else {
      selectedLayers.value = []
    }
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
  }

  // Check if source is currently active
  function isSourceEnabled(sourceId: string): boolean {
    return activeSources.value.includes(sourceId)
  }

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
    isSourceEnabled
  }
})
