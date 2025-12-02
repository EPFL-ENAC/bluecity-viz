<script setup lang="ts">
import MapLibreMap from '@/components/MapLibreMap.vue'
import DeckGLOverlay from '@/components/DeckGLOverlay.vue'
import LegendMap from '@/components/LegendMap.vue'
import MapControlsPanel from '@/components/MapControlsPanel.vue'
import EdgeTooltip from '@/components/EdgeTooltip.vue'
import { useMapLogic } from '@/composables/useMapLogic'
import { useDeckGLTrafficAnalysis } from '@/composables/useDeckGLTrafficAnalysis'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { inject, watch, onMounted, type Ref } from 'vue'

// Use the map logic composable
const { map, parameters, center, zoom, syncAllLayersVisibility, layersStore } = useMapLogic()

// Use the traffic analysis store
const trafficStore = useTrafficAnalysisStore()

// Use Deck.gl traffic analysis
const deckGLTraffic = useDeckGLTrafficAnalysis()

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

// Handle Deck.gl hover events for tooltips
function handleDeckHover(info: any) {
  deckGLTraffic.handleHover(info)
}

// Setup edge click callback (always active when traffic panel is open)
function setupEdgeClickCallback() {
  deckGLTraffic.setEdgeClickCallback((u, v, name) => {
    trafficStore.cycleEdgeModification(u, v, name)
  })
}

// Watch for traffic panel open/close
watch(
  () => trafficStore.isOpen,
  async (isOpen) => {
    if (isOpen) {
      await deckGLTraffic.loadGraphEdges()
      setupEdgeClickCallback()
    } else {
      deckGLTraffic.clearRoutes()
    }
  }
)

// Watch for edge modifications changes
watch(
  () => trafficStore.edgeModifications,
  () => {
    if (trafficStore.isOpen && !trafficStore.isRestoring) {
      deckGLTraffic.updateModifiedEdges()
    }
  },
  { deep: true }
)

// Watch for edge usage changes
watch(
  () =>
    [
      trafficStore.originalEdgeUsage,
      trafficStore.newEdgeUsage,
      trafficStore.activeVisualization
    ] as const,
  ([originalUsage, newUsage, activeVis]) => {
    if (trafficStore.isRestoring) return // Skip during batch restore

    if (originalUsage.length > 0 && trafficStore.isOpen && activeVis !== 'none') {
      deckGLTraffic.visualizeEdgeUsage(newUsage)
    } else if (activeVis === 'none') {
      deckGLTraffic.clearRoutes()
    }
  }
)

// Watch for restoration complete to trigger visualization update
watch(
  () => trafficStore.isRestoring,
  (isRestoring, wasRestoring) => {
    // When restoration completes (false after being true), update visualization
    if (!isRestoring && wasRestoring) {
      const originalUsage = trafficStore.originalEdgeUsage
      const newUsage = trafficStore.newEdgeUsage
      const activeVis = trafficStore.activeVisualization

      if (trafficStore.isOpen) {
        // Update modified edges visualization
        deckGLTraffic.updateModifiedEdges()

        // Update traffic visualization
        if (originalUsage.length > 0 && activeVis !== 'none') {
          deckGLTraffic.visualizeEdgeUsage(newUsage)
        } else if (activeVis === 'none') {
          deckGLTraffic.clearRoutes()
        }
      }
    }
  }
)

onMounted(async () => {
  if (trafficStore.isOpen) {
    await deckGLTraffic.loadGraphEdges()
    setupEdgeClickCallback()

    // Restore modified edges visualization if any exist
    if (trafficStore.edgeModifications.size > 0) {
      deckGLTraffic.updateModifiedEdges()
    }

    // Restore traffic visualization if data exists
    const activeVis = trafficStore.activeVisualization
    if (trafficStore.originalEdgeUsage.length > 0 && activeVis !== 'none') {
      deckGLTraffic.visualizeEdgeUsage(trafficStore.newEdgeUsage)
    }
  }
})
</script>

<template>
  <div class="visualizations-panel position-relative fill-height">
    <!-- MapLibre Map (always shown as base layer) -->
    <MapLibreMap
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

    <!-- Deck.gl Canvas (always mounted, shows layers only when traffic analysis is active) -->
    <DeckGLOverlay
      :layers="trafficStore.isOpen ? deckGLTraffic.layers.value : []"
      :on-click="handleDeckClick"
      :on-hover="handleDeckHover"
    />

    <!-- Edge Tooltip -->
    <EdgeTooltip :data="deckGLTraffic.tooltipData.value" />

    <!-- Unified Map Controls (Layers + Traffic Analysis) -->
    <MapControlsPanel />
  </div>
</template>

<style scoped>
.visualizations-panel {
  position: relative;
}
</style>
