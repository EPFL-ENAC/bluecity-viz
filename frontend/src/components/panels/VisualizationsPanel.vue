<script setup lang="ts">
import MapLibreMap from '@/components/MapLibreMap.vue'
import DeckGLOverlay from '@/components/DeckGLOverlay.vue'
import LegendMap from '@/components/LegendMap.vue'
import MapControlsPanel from '@/components/MapControlsPanel.vue'
import EdgeTooltip from '@/components/EdgeTooltip.vue'
import CVRPTooltip from '@/components/CVRPTooltip.vue'
import { useMapLogic } from '@/composables/useMapLogic'
import { useDeckGLTrafficAnalysis } from '@/composables/useDeckGLTrafficAnalysis'
import { useDeckGLCVRP } from '@/composables/useDeckGLCVRP'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { useCVRPStore } from '@/stores/cvrp'
import { inject, watch, onMounted, computed, type Ref } from 'vue'

// Use the map logic composable
const { map, parameters, center, zoom, syncAllLayersVisibility, layersStore } = useMapLogic()

// Use the traffic analysis store
const trafficStore = useTrafficAnalysisStore()
const cvrpStore = useCVRPStore()

// Use Deck.gl traffic analysis
const deckGLTraffic = useDeckGLTrafficAnalysis()

// Use Deck.gl CVRP layers
const deckGLCVRP = useDeckGLCVRP(deckGLTraffic.edgeMap)

// Combined layers for Deck.gl overlay.
// When CVRP has results, suppress the colored traffic route analysis layers so they
// don't clutter the waste collection view. Keep the grey base network and modification
// indicators so the user still sees which edges are modified.
const combinedLayers = computed(() => {
  const trafficLayers = (trafficStore.isOpen || cvrpStore.isOpen) ? deckGLTraffic.layers.value : []
  const filteredTrafficLayers = cvrpStore.hasResult
    ? trafficLayers.filter((l: any) => !l.id.startsWith('traffic-routes'))
    : trafficLayers
  return [...filteredTrafficLayers, ...deckGLCVRP.layers.value]
})

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

// Handle Deck.gl hover events for tooltips.
// When CVRP results are active, suppress the traffic edge tooltip — the CVRP route
// layer handles its own hover via the onHover callback on the PathLayer.
function handleDeckHover(info: any) {
  if (!cvrpStore.hasResult) {
    deckGLTraffic.handleHover(info)
  }
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

// Watch for CVRP panel open/close
watch(
  () => cvrpStore.isOpen,
  async (isOpen) => {
    if (isOpen) {
      await deckGLTraffic.loadGraphEdges()
      setupEdgeClickCallback()
    } else {
      cvrpStore.clearResult()
    }
  }
)

// Watch for edge modifications changes
watch(
  () => trafficStore.edgeModifications,
  () => {
    if ((trafficStore.isOpen || cvrpStore.isOpen) && !trafficStore.isRestoring) {
      deckGLTraffic.updateModifiedEdges()
    }
  },
  { deep: true }
)

// Watch for edge usage changes (also re-runs when infrastructure filters change)
watch(
  () =>
    [
      trafficStore.originalEdgeUsage,
      trafficStore.newEdgeUsage,
      trafficStore.activeVisualization,
      trafficStore.filterBusRoutes,
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
  await deckGLTraffic.loadGraphEdges()
  if (trafficStore.isOpen || cvrpStore.isOpen) {
    setupEdgeClickCallback()

    // Restore modified edges visualization if any exist
    if (trafficStore.edgeModifications.size > 0) {
      deckGLTraffic.updateModifiedEdges()
    }
  }

  if (trafficStore.isOpen) {
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

    <!-- Deck.gl Canvas (traffic analysis + CVRP layers) -->
    <DeckGLOverlay
      :layers="combinedLayers"
      :on-click="handleDeckClick"
      :on-hover="handleDeckHover"
    />

    <!-- Edge Tooltip (traffic analysis) -->
    <EdgeTooltip :data="deckGLTraffic.tooltipData.value" />

    <!-- CVRP Route Tooltip -->
    <CVRPTooltip :data="deckGLCVRP.cvrpTooltipData.value" />

    <!-- Unified Map Controls (Layers + Traffic Analysis) -->
    <MapControlsPanel />
  </div>
</template>

<style scoped>
.visualizations-panel {
  position: relative;
}
</style>
