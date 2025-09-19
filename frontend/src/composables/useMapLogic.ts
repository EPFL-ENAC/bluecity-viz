import MapLibreMap from '@/components/MapLibreMap.vue'
import { useLayersStore } from '@/stores/layers'
import { ref, shallowRef, watch } from 'vue'

// Import types
import type { Parameters } from '@/utils/jsonWebMap'

/**
 * Composable for handling map logic and state
 */
export function useMapLogic() {
  // Map reference
  const map = ref<InstanceType<typeof MapLibreMap>>()

  // Map parameters
  const parameters = shallowRef<Parameters>({})

  // Layers store
  const layersStore = useLayersStore()

  // Map configuration
  const center = {
    lat: 46.52,
    lng: 6.63
  }

  const zoom = 11

  // Sync layer visibility with the map when the selected layers change
  const syncAllLayersVisibility = (layersSelected: string[]) => {
    for (const { id: layerID } of layersStore.possibleLayers) {
      if (layersSelected.includes(layerID)) {
        map.value?.setLayerVisibility(layerID, true)
      } else {
        map.value?.setLayerVisibility(layerID, false)
      }
    }
  }

  // Watch for layer selection changes
  watch(() => layersStore.selectedLayers, syncAllLayersVisibility, { immediate: true, deep: true })

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
