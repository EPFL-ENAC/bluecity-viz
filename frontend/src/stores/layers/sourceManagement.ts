import type { CustomSourceSpecification } from '@/config/layerTypes'
import { mapConfig } from '@/config/mapConfig'
import { computed, type Ref } from 'vue'

export function createSourceManagement(
  availableResourceSources: Ref<string[]>,
  activeSources: Ref<string[]>,
  selectedLayers: Ref<string[]>,
  getLayersBySource: (sourceId: string) => any[],
  updateCurrentInvestigation: () => void
) {
  // Get list of all available sources
  const availableSources = computed((): CustomSourceSpecification[] => {
    return mapConfig.sources
  })

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

  // Toggle source active state
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
      // For now, also remove all layers from this source
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

  return {
    availableSources,
    availableResourceSourceObjects,
    availableSourcesForDialog,
    addSources,
    removeSource,
    toggleSource,
    isSourceEnabled,
    updateAvailableResourceSources,
    updateActiveSources
  }
}
