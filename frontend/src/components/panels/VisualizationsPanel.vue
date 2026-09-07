<script setup lang="ts">
import MapLibreMap from '@/components/MapLibreMap.vue'
import LegendMap from '@/components/LegendMap.vue'
import TrafficDock from '@/components/dock/TrafficDock.vue'
import CvrpDock from '@/components/dock/CvrpDock.vue'
import { useMapLogic } from '@/composables/useMapLogic'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { useCVRPStore } from '@/stores/cvrp'
import { defineAsyncComponent, inject, watch, computed, ref, type Ref } from 'vue'

// Use the map logic composable
const { map, parameters, center, zoom, syncAllLayersVisibility, layersStore } = useMapLogic()

// Use the traffic analysis store
const trafficStore = useTrafficAnalysisStore()
const cvrpStore = useCVRPStore()

// The whole deck.gl stack is a separate chunk, loaded the first time a tool is
// opened. Before that the page does not fetch the 6 MB road network at all.
const DeckAnalysisLayer = defineAsyncComponent(() => import('./DeckAnalysisLayer.vue'))

const anyToolOpen = computed(() => trafficStore.isOpen || cvrpStore.isOpen)

// Once mounted it stays mounted: taking the deck.gl overlay off the map and
// putting it back leaks a maplibre render listener each time, and rebuilding
// the overlay throws away the GPU buffers for nothing. Closing every tool
// empties the layer list instead.
const deckMounted = ref(false)
watch(
  anyToolOpen,
  (open) => {
    if (open) deckMounted.value = true
  },
  { immediate: true }
)

// Get the provided map ref from parent
const mapComponentRef = inject<Ref<any>>('mapRef')

// Watch map changes and update the provided ref
watch(
  map,
  (newMap) => {
    if (mapComponentRef) {
      mapComponentRef.value = newMap
    }
  },
  { immediate: true }
)

// Closing the waste collection tool throws its result away. This lives here,
// not in the deck.gl child, so it still runs when that child is not mounted.
watch(
  () => cvrpStore.isOpen,
  (isOpen) => {
    if (!isOpen) cvrpStore.clearResult()
  }
)
</script>

<template>
  <div class="visualizations-panel">
    <!-- MapLibre Map (always shown as base layer) -->
    <MapLibreMap
      ref="map"
      :center="center"
      :popup-layer-ids="parameters.popupLayerIds"
      :zoom="zoom"
      :max-zoom="20"
      :min-zoom="6"
      :callback-loaded="() => syncAllLayersVisibility(layersStore.selectedLayers)"
    >
      <template #legend>
        <legend-map :layers="layersStore.visibleLayers"></legend-map>
      </template>
    </MapLibreMap>

    <!-- Deck.gl canvas, tooltips and analysis layers -->
    <DeckAnalysisLayer v-if="deckMounted" />

    <!-- Analysis dock, on the right edge of the map, only when a tool is open -->
    <div v-if="anyToolOpen" class="dock">
      <TrafficDock v-if="trafficStore.isOpen" />
      <CvrpDock v-else />
    </div>
  </div>
</template>

<style scoped>
.visualizations-panel {
  position: absolute;
  inset: 0;
}

.dock {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: var(--bc-dock-w);
  background: var(--bc-panel-translucent);
  border-left: 1px solid var(--bc-line);
  overflow-y: auto;
  z-index: 2;
}
</style>
