import type { CustomSourceSpecification } from '@/config/layerTypes'
import { mapConfig } from '@/config/mapConfig'
import { computed, type Ref } from 'vue'

export function createLayerManagement(
  selectedLayers: Ref<string[]>,
  layerGroups: Ref<any[]>,
  expandedGroups: Ref<Record<string, boolean>>,
  updateCurrentInvestigation: () => void
) {
  // Flatten all layers for internal use
  const possibleLayers = computed(() => {
    return layerGroups.value.flatMap((group) =>
      group.layers.map((layer: any) => ({
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

  return {
    possibleLayers,
    visibleLayers,
    layersBySource,
    getLayersBySource,
    toggleGroup,
    isGroupVisible,
    toggleGroupVisibility,
    updateSelectedLayers,
    updateSingleLayerSelection
  }
}
