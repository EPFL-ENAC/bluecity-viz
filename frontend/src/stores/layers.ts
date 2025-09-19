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

  // Selected source IDs for the resources panel
  const selectedSources = ref<string[]>([])

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

  // Get selected source objects
  const selectedSourceObjects = computed(() => {
    return mapConfig.sources.filter((source) => selectedSources.value.includes(source.id))
  })

  // Get available sources that aren't already selected
  const availableSourcesForDialog = computed(() => {
    return mapConfig.sources.filter((source) => !selectedSources.value.includes(source.id))
  })

  // Add sources from dialog
  function addSources(sourceIds: string[]) {
    selectedSources.value = [...selectedSources.value, ...sourceIds]
  }

  // Remove a source
  function removeSource(sourceId: string) {
    selectedSources.value = selectedSources.value.filter((id) => id !== sourceId)
    // Also remove any layers from this source when source is removed
    const layersFromSource = getLayersBySource(sourceId)
    const layerIds = layersFromSource.map((layer) => layer.layer.id)
    selectedLayers.value = selectedLayers.value.filter((id) => !layerIds.includes(id))
  }

  // Toggle source visibility (enable/disable layers from this source)
  function toggleSource(sourceId: string, enabled: boolean | null) {
    if (enabled === null) return

    const layersFromSource = getLayersBySource(sourceId)
    const layerIds = layersFromSource.map((layer) => layer.layer.id)

    if (enabled) {
      // Add layers from this source
      const newSelection = [...selectedLayers.value, ...layerIds]
      updateSelectedLayers([...new Set(newSelection)]) // Remove duplicates
    } else {
      // Remove layers from this source
      const filteredLayers = selectedLayers.value.filter((id) => !layerIds.includes(id))
      updateSelectedLayers(filteredLayers)
    }
  }

  // Check if source is currently enabled (has visible layers)
  function isSourceEnabled(sourceId: string): boolean {
    const layersFromSource = getLayersBySource(sourceId)
    const layerIds = layersFromSource.map((layer) => layer.layer.id)
    return layerIds.some((id) => selectedLayers.value.includes(id))
  }

  return {
    layerGroups,
    sp0Period,
    selectedLayers,
    selectedSources,
    filteredCategories,
    expandedGroups,
    possibleLayers,
    visibleLayers,
    availableSources,
    layersBySource,
    selectedSourceObjects,
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
