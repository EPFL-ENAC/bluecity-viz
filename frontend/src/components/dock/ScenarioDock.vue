<script setup lang="ts">
import AreaPicker from '@/components/dock/AreaPicker.vue'
import CvrpTab from '@/components/dock/CvrpTab.vue'
import RoutingTab from '@/components/dock/RoutingTab.vue'
import BcIcon from '@/components/ui/BcIcon.vue'
import { useAreaFeedback } from '@/composables/useAreaFeedback'
import { useGraphEdges } from '@/composables/useGraphEdges'
import { useLayersStore } from '@/stores/layers'
import { useScenarioStore, type StreetRef } from '@/stores/scenario'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import type { Map as MapLibre } from 'maplibre-gl'
import { computed, inject, type Ref } from 'vue'

/**
 * The analysis dock.
 *
 * It shows the tool picked in the sidebar (Analytics tools). The modified edges
 * are shared: routing and waste collection both answer the same question about
 * the same graph, each keeps its own result and its own stale state.
 *
 * Each tool is a storyline of three steps (Model, Scenario, Results). The
 * modified edges live in the Scenario step, so the dock itself only holds the
 * area and the tool.
 */

const emit = defineEmits<{
  (event: 'hover-route', routeId: number | null): void
  (event: 'focus', keys: string[], select?: StreetRef): void
}>()

const layersStore = useLayersStore()
const trafficStore = useTrafficAnalysisStore()
const scenarioStore = useScenarioStore()
const areaFeedback = useAreaFeedback()
const mapRef = inject<Ref<{ map?: MapLibre } | undefined>>('mapRef')

// The area the workbench runs on.
const areaName = computed(() => {
  const circle = trafficStore.area
  if (!circle) return 'Lausanne (default)'
  // The name the picker read on the basemap. Areas saved before that, and the
  // styles with no labels, still show the circle itself.
  if (circle.name) return circle.name
  const km = (circle.radiusM / 1000).toFixed(1)
  return `${km} km around ${circle.lat.toFixed(3)}, ${circle.lon.toFixed(3)}`
})

// The circle behind the name, so the radius stays readable.
const areaShape = computed(() => {
  const circle = trafficStore.area
  if (!circle?.name) return ''
  const km = (circle.radiusM / 1000).toFixed(1)
  return `${km} km around ${circle.lat.toFixed(3)}, ${circle.lon.toFixed(3)}`
})

// The streets of this area are not on the map yet. The ring is already
// there, so the dock says why it is empty instead of looking broken.
const { edges: graphEdges } = useGraphEdges()
const areaStatus = computed(() => {
  if (trafficStore.areaError) return null
  if (trafficStore.isBuildingArea) return 'Building the network for this area…'
  if (graphEdges.value.length === 0) return 'Loading the streets…'
  return null
})

/** Open the picker on the circle we have, or on what the map is looking at. */
function changeArea(): void {
  const centre = mapRef?.value?.map?.getCenter()
  trafficStore.enterPickMode(centre ? { lon: centre.lng, lat: centre.lat } : undefined)
}

const title = computed(() => layersStore.activeInvestigation?.name ?? 'Road closure scenario')

const toolName = computed(() =>
  scenarioStore.activeTab === 'cvrp' ? 'Waste collection' : 'Routing'
)
</script>

<template>
  <AreaPicker
    v-if="trafficStore.pickMode"
    :feedback="areaFeedback.feedback.value"
    :can-use="areaFeedback.canUse.value"
    :is-checking="areaFeedback.isChecking.value"
    :limits="areaFeedback.limits.value"
  />

  <div v-else class="dock-panel">
    <div class="dock-head">
      <div class="dock-head__top">
        <span class="bc-micro">{{ toolName }}</span>
        <button class="dock-close" title="Close the tool" @click="scenarioStore.isOpen = false">
          <BcIcon name="x" />
        </button>
      </div>
      <div class="dock-title">{{ title }}</div>
    </div>

    <!-- The area both tools run on. Not a step of the storyline: it is set
         before any tool, and it never dims. -->
    <div class="dock-section">
      <div class="dock-section__head">
        <span class="bc-micro">Area</span>
        <button class="bc-micro clear-btn" @click="changeArea">Change area</button>
      </div>
      <div class="area-name">{{ areaName }}</div>
      <p v-if="areaShape" class="bc-empty area-note">{{ areaShape }}</p>
      <p v-if="areaStatus" class="bc-empty area-note">{{ areaStatus }}</p>
      <p v-if="trafficStore.areaError" class="bc-empty area-error">
        {{ trafficStore.areaError.message }}
      </p>
    </div>

    <!-- The tool picked in the sidebar, as its storyline. The modified edges
         live in its Scenario step. -->
    <RoutingTab
      v-if="scenarioStore.activeTab === 'routing'"
      @focus="(keys, select) => emit('focus', keys, select)"
    />
    <p v-else-if="trafficStore.area" class="bc-empty dock-section">
      Waste collection runs on Lausanne only, it needs the bin data. Set the area back to Lausanne
      to use it.
    </p>
    <CvrpTab
      v-else
      @hover-route="(id) => emit('hover-route', id)"
      @focus="(keys, select) => emit('focus', keys, select)"
    />
  </div>
</template>

<style scoped>
.dock-head {
  padding: 18px 22px 14px;
  border-bottom: 1px solid var(--bc-line);
}

.dock-head__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.dock-close {
  display: flex;
  padding: 2px;
  background: none;
  border: 0;
  color: var(--bc-grey);
  cursor: pointer;
}

.dock-close:hover {
  color: var(--bc-ink);
}

.dock-title {
  font-size: var(--bc-fs-title);
  font-weight: 300;
  letter-spacing: -0.01em;
  margin-top: 4px;
}

.dock-section {
  padding: 16px 22px;
  border-bottom: 1px solid var(--bc-line);
}

.dock-section__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 4px;
}

.area-name {
  font-size: var(--bc-fs-body);
  padding: 4px 0 0;
}

.area-note {
  margin: 6px 0 0;
}

.area-error {
  margin: 6px 0 0;
  color: var(--bc-danger);
}

.clear-btn {
  background: none;
  border: 0;
  padding: 0;
  cursor: pointer;
}

.clear-btn:hover {
  color: var(--bc-ink);
}
</style>
