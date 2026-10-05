<script setup lang="ts">
import AreaPicker from '@/components/dock/AreaPicker.vue'
import CvrpTab from '@/components/dock/CvrpTab.vue'
import RoutingTab from '@/components/dock/RoutingTab.vue'
import BcIcon from '@/components/ui/BcIcon.vue'
import { useAreaFeedback } from '@/composables/useAreaFeedback'
import { useGraphEdges } from '@/composables/useGraphEdges'
import { useLayersStore } from '@/stores/layers'
import type { TrafficAreaSelection } from '@/stores/layers/types'
import { useScenarioStore, type StreetRef } from '@/stores/scenario'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { computed, watch } from 'vue'

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

// The area the workbench runs on.
// The name the picker wrote, else the one the server gave once the area is
// built (communes picked with no local index). Areas saved before names, and
// the styles with no labels, still show the shape itself.
const namedAs = computed(() => trafficStore.area.name || trafficStore.areaInfo?.name || '')

const areaName = computed(() => namedAs.value || areaShapeOf(trafficStore.area))

// The shape behind the name, so the radius or the commune count stays readable.
const areaShape = computed(() => (namedAs.value ? areaShapeOf(trafficStore.area) : ''))

function areaShapeOf(area: TrafficAreaSelection): string {
  if (area.kind === 'municipalities') {
    const n = area.ofsIds.length
    return n === 1 ? '1 municipality' : `${n} municipalities`
  }
  const km = (area.radiusM / 1000).toFixed(1)
  return `${km} km around ${area.lat.toFixed(3)}, ${area.lon.toFixed(3)}`
}

// The streets of this area are not on the map yet. The ring is already
// there, so the dock says why it is empty instead of looking broken.
const { edges: graphEdges } = useGraphEdges()
const areaStatus = computed(() => {
  if (trafficStore.areaError) return null
  if (trafficStore.isBuildingArea) return 'Building the network for this area…'
  if (graphEdges.value.length === 0) return 'Loading the streets…'
  if (!trafficStore.areaReady)
    return 'Routing the trips of this area. The map shows the betweenness of its streets meanwhile.'
  return null
})

// The dock needs the server's word on the area: the waste tool runs there or
// not (areaInfo.cvrp). The map can show the streets from its cache without
// asking, so ask here too. A failure lands in areaError, shown below.
watch(
  () => trafficStore.graphKey,
  () => {
    trafficStore.ensureArea().catch(() => {})
  },
  { immediate: true }
)

/** Open the picker on the area we have. */
function changeArea(): void {
  trafficStore.enterPickMode()
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
    :communes="areaFeedback.communes.value"
    :outline="areaFeedback.lastOutline.value"
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
    <!-- The server says if the waste tool runs here: it needs the Lausanne
         bins and streets. While the area is building, the Area section above
         already says so. -->
    <CvrpTab
      v-else-if="trafficStore.areaInfo?.cvrp"
      @hover-route="(id) => emit('hover-route', id)"
      @focus="(keys, select) => emit('focus', keys, select)"
    />
    <p v-else-if="trafficStore.areaInfo" class="bc-empty dock-section">
      Waste collection runs on Lausanne only, it needs the bin data. Set the area back to Lausanne
      to use it.
    </p>
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
