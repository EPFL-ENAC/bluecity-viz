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

  return {
    layerGroups,
    sp0Period,
    selectedLayers,
    filteredCategories,
    expandedGroups,
    possibleLayers,
    visibleLayers,
    toggleGroup,
    isGroupVisible,
    filterOutCategories,
    toggleGroupVisibility,
    updateSelectedLayers,
    updateSingleLayerSelection
  }
})
