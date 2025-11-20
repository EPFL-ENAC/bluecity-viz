<script setup lang="ts">
import MapLibreMap from '@/components/MapLibreMap.vue'
import DeckGLOverlay from '@/components/DeckGLOverlay.vue'
import LegendMap from '@/components/LegendMap.vue'
import LayerSelector from '@/components/LayerSelector.vue'
import { useMapLogic } from '@/composables/useMapLogic'
import { useDeckGLTrafficAnalysis } from '@/composables/useDeckGLTrafficAnalysis'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { inject, watch, onMounted, computed, type Ref } from 'vue'

// Use the map logic composable
const { map, parameters, center, zoom, syncAllLayersVisibility, layersStore } = useMapLogic()

// Use the traffic analysis store
const trafficStore = useTrafficAnalysisStore()

// Use Deck.gl traffic analysis
const deckGLTraffic = useDeckGLTrafficAnalysis()

// Create stable view state for Deck.gl to prevent constant recreation
const deckViewState = computed(() => ({
  longitude: center.lng,
  latitude: center.lat,
  zoom: zoom,
  pitch: 0,
  bearing: 0
}))

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

// Handle Deck.gl click events
function handleDeckClick(info: any) {
  deckGLTraffic.handleClick(info)
}

// Watch for traffic panel open/close
watch(
  () => trafficStore.isOpen,
  async (isOpen) => {
    if (isOpen) {
      await deckGLTraffic.loadGraphEdges()
      deckGLTraffic.setEdgeClickCallback((u, v) => {
        trafficStore.addRemovedEdge(u, v)
      })
    } else {
      deckGLTraffic.clearRoutes()
    }
  }
)

// Watch for removed edges changes
watch(
  () => trafficStore.removedEdgesArray,
  (removedEdges) => {
    if (trafficStore.isOpen) {
      deckGLTraffic.updateRemovedEdges(removedEdges)
    }
  }
)

// Watch for edge usage changes
watch(
  () => [trafficStore.originalEdgeUsage, trafficStore.newEdgeUsage],
  ([originalUsage, newUsage]) => {
    if (originalUsage.length > 0 && trafficStore.isOpen) {
      deckGLTraffic.visualizeEdgeUsage(originalUsage, newUsage)
    }
  }
)

onMounted(async () => {
  if (trafficStore.isOpen) {
    await deckGLTraffic.loadGraphEdges()
  }
})
</script>

<template>
  <div class="visualizations-panel position-relative fill-height">
    <!-- MapLibre Map (shown when traffic analysis is NOT active) -->
    <MapLibreMap
      v-show="!trafficStore.isOpen"
      ref="map"
      :center="center"
      :popup-layer-ids="parameters.popupLayerIds"
      :zoom="zoom"
      :max-zoom="20"
      :min-zoom="6"
      :callback-loaded="() => syncAllLayersVisibility(layersStore.selectedLayers)"
      class="fill-height"
    >
      <template #legend>
        <legend-map :layers="layersStore.visibleLayers"></legend-map>
      </template>
    </MapLibreMap>

    <!-- Deck.gl Canvas (shown when traffic analysis IS active) -->
    <DeckGLOverlay
      v-show="trafficStore.isOpen"
      :layers="deckGLTraffic.layers.value"
      :view-state="deckViewState"
      :on-click="handleDeckClick"
      class="fill-height"
    />

    <!-- Layer Selector (only shown when MapLibre is active) -->
    <LayerSelector v-show="!trafficStore.isOpen" />
  </div>
</template>

<style scoped>
.visualizations-panel {
  position: relative;
}
</style>
