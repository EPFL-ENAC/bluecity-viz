import MapLibreMap from '@/components/MapLibreMap.vue'
import { useLayersStore } from '@/stores/layers'
import { shallowRef, watch } from 'vue'

/** Extra map settings. Nothing fills them today, the map uses its defaults. */
export interface MapParameters {
  popupLayerIds?: string[]
}

/**
 * Composable for handling map logic and state
 */
export function useMapLogic() {
  // Map reference
  const map = shallowRef<InstanceType<typeof MapLibreMap>>()

  // Map parameters
  const parameters: MapParameters = {}

  // Layers store
  const layersStore = useLayersStore()

  // Map configuration
  const center = {
    lat: 46.52,
    lng: 6.63
  }

  const zoom = 11

  /**
   * Put every layer of the config in the state the selection asks for.
   * Used on first load and after a basemap change, when we know nothing
   * about what the map already shows.
   */
  const syncAllLayersVisibility = (layersSelected: string[]) => {
    const selected = new Set(layersSelected)
    for (const { id: layerID } of layersStore.possibleLayers) {
      map.value?.setLayerVisibility(layerID, selected.has(layerID))
    }
  }

  /** Only touch the layers the user just checked or unchecked. */
  const applySelectionDiff = (selected: string[], previous: string[] = []) => {
    const next = new Set(selected)
    const before = new Set(previous)

    for (const layerID of next) {
      if (!before.has(layerID)) map.value?.setLayerVisibility(layerID, true)
    }
    for (const layerID of before) {
      if (!next.has(layerID)) map.value?.setLayerVisibility(layerID, false)
    }
  }

  // Watch for layer selection changes. The copy tracks the length and every
  // index, so an in place change in the store still fires the watcher.
  watch(() => layersStore.selectedLayers.slice(), applySelectionDiff)

  // Return all values and functions needed by the component
  return {
    // Refs
    map,
    parameters,

    // Constants
    center,
    zoom,

    // Functions
    syncAllLayersVisibility,

    // Stores
    layersStore
  }
}
