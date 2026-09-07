<script setup lang="ts">
import LegendMap from '@/components/LegendMap.vue'
import MapLibreMap from '@/components/MapLibreMap.vue'
import ScenarioDock from '@/components/dock/ScenarioDock.vue'
import GraphOverlay from '@/components/map/GraphOverlay.vue'
import { useMapLogic } from '@/composables/useMapLogic'
import { useCVRPStore } from '@/stores/cvrp'
import { useScenarioStore } from '@/stores/scenario'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { computed, inject, ref, watch, type Ref } from 'vue'

// Use the map logic composable
const { map, parameters, center, zoom, syncAllLayersVisibility, layersStore } = useMapLogic()

const trafficStore = useTrafficAnalysisStore()
const cvrpStore = useCVRPStore()
const scenarioStore = useScenarioStore()

const anyToolOpen = computed(() => scenarioStore.isOpen)

// The graph overlay pulls the 6 MB road network, so it is only mounted once a
// tool asks for it. Once mounted it stays: its maplibre layers cost nothing
// when no tool is open, and remounting would re-tile the source for nothing.
const graphMounted = ref(false)
watch(
  anyToolOpen,
  (open) => {
    if (open) graphMounted.value = true
  },
  { immediate: true }
)

const graphOverlay = ref<InstanceType<typeof GraphOverlay> | null>(null)

/** A dock row hovering a vehicle lights that route on the map. */
function hoverRoute(routeId: number | null) {
  graphOverlay.value?.hoverRoute(routeId)
}

/** The scenario block asking the map to fit some streets. */
function focusStreets(keys: string[]) {
  graphOverlay.value?.focus(keys)
}

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

// The workbench owns whether the tools are open. Both stores follow it, so a
// restored session cannot end up with a tool "open" and no dock on screen.
watch(
  () => scenarioStore.isOpen,
  (isOpen, wasOpen) => {
    trafficStore.isOpen = isOpen
    cvrpStore.isOpen = isOpen
    if (isOpen) return

    scenarioStore.select(null)
    // Closing the workbench throws the waste collection result away. Not on
    // the first run: a restored session was never open, it just loaded.
    if (wasOpen) cvrpStore.clearResult()
  },
  { immediate: true }
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

    <!-- The street graph, the result, the routes, the hover card and the editor -->
    <GraphOverlay
      v-if="graphMounted"
      ref="graphOverlay"
      :class="{ 'is-docked': anyToolOpen }"
    />

    <!-- The scenario workbench, on the right edge of the map -->
    <div v-if="anyToolOpen" class="dock">
      <ScenarioDock @hover-route="hoverRoute" @focus="focusStreets" />
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
