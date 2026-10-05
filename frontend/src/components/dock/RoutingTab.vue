<script setup lang="ts">
import EffectRow, { type EffectState } from '@/components/dock/EffectRow.vue'
import LayerRows, { visLabel } from '@/components/dock/LayerRows.vue'
import ScenarioEdges from '@/components/dock/ScenarioEdges.vue'
import StoryStep from '@/components/dock/StoryStep.vue'
import ImpactStatistics from '@/components/ImpactStatistics.vue'
import BcIcon from '@/components/ui/BcIcon.vue'
import BcRow from '@/components/ui/BcRow.vue'
import BcSeg from '@/components/ui/BcSeg.vue'
import BcSlider from '@/components/ui/BcSlider.vue'
import { useDeltaBars } from '@/composables/useDeltaBars'
import { useGraphEdges } from '@/composables/useGraphEdges'
import { useMapView } from '@/composables/useMapView'
import { useModelPreview } from '@/composables/useModelPreview'
import { ApiError, recalculateRoutes, type NodeWeighting } from '@/services/trafficAnalysis'
import { useScenarioStore, type StreetRef } from '@/stores/scenario'
import { useStorylineStore } from '@/stores/storyline'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { computed, onMounted, ref, watch } from 'vue'

// The routing tool as one storyline of three steps: set the model, edit the
// network and run, then read the map and the numbers. The modified edges are
// shared with the waste collection tool.

const emit = defineEmits<{
  (event: 'focus', keys: string[], select?: StreetRef): void
}>()

const trafficStore = useTrafficAnalysisStore()
const { hasBus } = useGraphEdges()
const scenarioStore = useScenarioStore()
const storyline = useStorylineStore()
const { absorbers, barWidth, deltaText } = useDeltaBars()

// The dock shows the tool whose row is picked in the sidebar, so the open step
// of the view is this tab's.
const { step } = useMapView()

// The Model step draws the routing of the chosen options, and follows them.
useModelPreview()

/** The wheel while the routes run, the tick once the result matches the scenario. */
const effectState = computed<EffectState>(() => {
  if (trafficStore.isCalculating) return 'running'
  if (trafficStore.hasCalculatedRoutes && !trafficStore.isStale) return 'done'
  return 'idle'
})

/** Fit the map on one street. */
function focus(key: string): void {
  emit('focus', [key])
}

const loadingMessage = ref('')
// Why the last run did not go through, when the user can do something about it.
const calculateError = ref<string | null>(null)

// The pair counts come from the server, not from a constant here. Each area
// has its own, so we ask again when the area changes.
function refreshGraphInfo() {
  trafficStore.loadGraphInfo().catch((error) => {
    console.error('Failed to load graph info:', error)
  })
}
onMounted(refreshGraphInfo)
watch(() => trafficStore.areaId, refreshGraphInfo)

function formatTrips(count: number): string {
  return count.toLocaleString('en-US')
}

// The two choices, hidden until we know the numbers.
const nodeWeightingOptions = [
  { value: 'uniform', label: 'Uniform' },
  { value: 'population', label: 'Population + jobs' }
]
// BcSeg speaks plain strings
const nodeWeighting = computed({
  get: () => trafficStore.nodeWeighting,
  set: (value: string) => (trafficStore.nodeWeighting = value as NodeWeighting)
})

const tripsOptions = computed(() => {
  const base = trafficStore.odPairsDefault
  const full = trafficStore.odPairsFull
  if (!base || !full) return []
  return [
    { value: 'default', label: `${formatTrips(base)} (default)` },
    { value: 'full', label: `${formatTrips(full)} (full)` }
  ]
})

// null and the default count are the same choice on screen.
const trips = computed({
  get: () => {
    const chosen = trafficStore.odPairs
    return chosen === null || chosen === trafficStore.odPairsDefault ? 'default' : 'full'
  },
  set: (value: string) => {
    trafficStore.setOdPairs(value === 'full' ? trafficStore.odPairsFull : null)
  }
})

// What we send: null means the server default, so use the number when we have it.
function chosenOdPairs(): number | undefined {
  return trafficStore.odPairs ?? trafficStore.odPairsDefault ?? undefined
}

const resultTrips = computed(() =>
  trafficStore.resultOdPairs === null ? '' : formatTrips(trafficStore.resultOdPairs)
)

/** The model in one line, for the folded Model step. */
const modelSummary = computed(() => {
  const parts: string[] = []
  const odPairs = chosenOdPairs()
  if (odPairs) parts.push(`${formatTrips(odPairs)} trips`)
  const n = trafficStore.congestionIterations
  parts.push(
    trafficStore.useCongestionModel
      ? `BPR, ${n} iteration${n > 1 ? 's' : ''}`
      : 'static betweenness'
  )
  if (trafficStore.elasticDemand) parts.push('elastic demand')
  if (trafficStore.nodeWeighting === 'population') parts.push('population + jobs')
  return parts.join(' · ')
})

const scenarioSummary = computed(() => {
  const n = scenarioStore.count
  const edges = n === 0 ? 'No street modified' : `${n} street${n > 1 ? 's' : ''} modified`
  if (step.value === 'model') return `${edges}. Validate the model to edit the network.`
  return trafficStore.isStale ? `${edges}, changed since the result` : edges
})

const resultsSummary = computed(() => {
  if (step.value === 'model') return 'Shown once the routes are calculated.'
  if (!trafficStore.hasCalculatedRoutes) return 'Calculate the routes to see them.'
  const mode = trafficStore.availableVisualizations.find(
    (vis) => vis.value === trafficStore.activeVisualization
  )
  const parts = [resultTrips.value && `${resultTrips.value} trips`]
  if (mode) parts.push(visLabel(mode.value, mode.label))
  return parts.filter(Boolean).join(' · ')
})

/** One line under the Model layers: what the map waits for, or why it did not come. */
const modelStatus = computed(() => {
  // the dock head already says the area is being built
  if (trafficStore.isBuildingArea) return ''
  if (trafficStore.modelLoading) {
    const odPairs = chosenOdPairs()
    return odPairs ? `Routing ${formatTrips(odPairs)} trips…` : 'Routing the trips…'
  }
  return trafficStore.modelError ? `The model did not load: ${trafficStore.modelError}` : ''
})

/**
 * The Model state and the run, both on the area the store points at. The
 * Model state is the left side of the comparison, whatever the model: the
 * same options on the untouched network.
 */
function runOnce(odPairs: number | undefined) {
  return Promise.all([
    trafficStore.loadModelState(),
    recalculateRoutes(scenarioStore.wire, {
      useCongestionModel: trafficStore.useCongestionModel,
      congestionIterations: trafficStore.congestionIterations,
      elasticDemand: trafficStore.elasticDemand,
      nodeWeighting: trafficStore.nodeWeighting,
      odPairs,
      areaId: trafficStore.areaId
    })
  ])
}

async function calculateRoutes() {
  const odPairs = chosenOdPairs()
  const trips = odPairs ? ` on ${formatTrips(odPairs)} trips` : ''

  const baseMessage = trafficStore.useCongestionModel
    ? `Congestion routing (${trafficStore.congestionIterations} iteration${
        trafficStore.congestionIterations > 1 ? 's' : ''
      })${trips}…`
    : `Calculating routes${trips}…`

  trafficStore.isCalculating = true
  loadingMessage.value = baseMessage
  calculateError.value = null
  try {
    // A picked area may not be on the server any more (restart, eviction). This
    // builds it back before we ask anything about it. The default one is
    // always there, so this is one quick round trip.
    if (!trafficStore.areaId) loadingMessage.value = 'Building the network for this area…'
    await trafficStore.ensureArea()
    loadingMessage.value = baseMessage

    // The Model state is the same for every run with these options, so it
    // comes from the store cache after the first time.
    let answer
    try {
      answer = await runOnce(odPairs)
    } catch (error) {
      // The area was dropped between the two calls: build it and try once more.
      if (!(error instanceof ApiError) || error.code !== 'area_not_loaded') throw error
      trafficStore.forgetAreaId()
      loadingMessage.value = 'Building the network for this area…'
      await trafficStore.ensureArea()
      loadingMessage.value = baseMessage
      answer = await runOnce(odPairs)
    }
    const [model, result] = answer

    // The options changed while we were waiting, this answer is for the old ones.
    if (!model || odPairs !== chosenOdPairs()) return

    if (model.odPairs !== result.od_pairs) {
      console.warn(`The Model state is on ${model.odPairs} pairs, the run on ${result.od_pairs}`)
    }

    trafficStore.setEdgeUsage(
      model.rows,
      result.new_edge_usage,
      result.impact_statistics,
      result.od_pairs,
      scenarioStore.hash
    )
  } catch (error) {
    // The area answered but its trips are not routed yet: the button waits
    // for it now, say so instead of failing quietly.
    if (error instanceof ApiError && error.code === 'area_not_ready') {
      calculateError.value = 'This area is still routing its trips. Calculate again in a moment.'
    } else {
      console.error('Failed to calculate routes:', error)
    }
  } finally {
    trafficStore.isCalculating = false
  }
}
</script>

<template>
  <StoryStep
    :step="1"
    title="Model"
    :state="step === 'model' ? 'open' : 'done'"
    action="Edit"
    :busy="trafficStore.isCalculating"
    @open="storyline.returnToInit('routing')"
  >
    <template #summary>
      {{ modelSummary
      }}<template v-if="trafficStore.hasCalculatedRoutes">. Editing it drops the result.</template>
    </template>
    <div class="dock-section">
      <div class="bc-micro dock-section__title">Routing model</div>

      <BcRow
        :on="trafficStore.useCongestionModel"
        @click="trafficStore.useCongestionModel = !trafficStore.useCongestionModel"
      >
        Iterative model (BPR congestion)
        <template #trailing>
          <v-tooltip location="right" max-width="320">
            <template #activator="{ props: tip }">
              <span v-bind="tip" class="info-icon" @click.stop><BcIcon name="info" /></span>
            </template>
            <div>
              <div class="font-weight-bold mb-1">Static betweenness vs. iterative volumes</div>
              <div class="mb-2">
                <strong>Off:</strong> only the trips that used a modified street are re-routed, on
                travel times derived from the betweenness of the modified network. Roads that
                structurally attract more flow appear slower, so the displaced traffic spreads
                instead of piling onto the one next-fastest street.
              </div>
              <div>
                <strong>On:</strong> every trip is re-routed, and the simulated volumes are
                normalised to daily vehicle-km and fed back into the BPR speed-reduction formula,
                repeating for the chosen number of iterations, converging toward a
                <em>Wardrop user equilibrium</em>. Slower, and the right choice when the travel-time
                numbers themselves matter.
              </div>
            </div>
          </v-tooltip>
        </template>
      </BcRow>

      <div v-if="trafficStore.useCongestionModel" class="iterations">
        <div class="iterations__label">Iterations ({{ trafficStore.congestionIterations }})</div>
        <BcSlider v-model="trafficStore.congestionIterations" :min="1" :max="3" :step="1" />
      </div>

      <BcRow
        :on="trafficStore.elasticDemand"
        @click="trafficStore.elasticDemand = !trafficStore.elasticDemand"
      >
        Elastic demand
        <template #trailing>
          <v-tooltip location="right" max-width="320">
            <template #activator="{ props: tip }">
              <span v-bind="tip" class="info-icon" @click.stop><BcIcon name="info" /></span>
            </template>
            <div>
              <div class="font-weight-bold mb-1">Elastic demand</div>
              <div>
                When on, the scenario draws the trip destinations again on its own travel times:
                travellers adapt, so closing a major road shifts trips to closer destinations rather
                than spiking total travel time. Origins stay put. Only the trips the scenario
                reaches move, the others keep their destination, so a scenario that changes nothing
                moves nothing. A moved trip cannot be compared with itself, so the impact panel
                shows totals only.
              </div>
            </div>
          </v-tooltip>
        </template>
      </BcRow>
      <p v-if="trafficStore.elasticDemand" class="trips__warning">
        It changes how the scenario is routed, not this map.
      </p>

      <div class="trips">
        <div class="bc-micro trips__label">Node weights</div>
        <BcSeg v-model="nodeWeighting" :options="nodeWeightingOptions" equal />
      </div>

      <div v-if="tripsOptions.length > 0" class="trips">
        <div class="bc-micro trips__label">Trips</div>
        <BcSeg
          v-model="trips"
          :options="tripsOptions"
          equal
          :class="{ 'trips__seg--busy': trafficStore.isCalculating }"
        />
        <p v-if="trips === 'full'" class="trips__warning">
          About 4x slower. Compared with the default, 85 of the 100 busiest roads are the same
          (frequency correlation 0.96).
        </p>
      </div>
    </div>

    <!-- The routing of these options on the untouched network: what the
         scenario is compared with. -->
    <div class="dock-section">
      <template v-if="trafficStore.hasModelState">
        <div class="bc-micro dock-section__title">Layers</div>
        <LayerRows />
      </template>
      <p v-if="modelStatus" class="bc-empty model-status">{{ modelStatus }}</p>

      <button class="bc-btn bc-btn--primary calculate" @click="storyline.validate('routing')">
        Validate initial model
      </button>
    </div>
  </StoryStep>

  <StoryStep
    :step="2"
    title="Scenario"
    :state="step === 'scenario' ? 'open' : step === 'model' ? 'todo' : 'done'"
    @open="scenarioStore.mapMode = 'scenario'"
  >
    <template #summary>{{ scenarioSummary }}</template>
    <p v-if="trafficStore.isStale" class="stale-banner">
      Scenario changed since the last result. Calculate again to update it.
    </p>
    <div class="dock-section">
      <ScenarioEdges @focus="(keys, select) => emit('focus', keys, select)" />

      <button
        class="bc-btn bc-btn--primary calculate"
        :disabled="trafficStore.isCalculating || !trafficStore.areaReady"
        @click="calculateRoutes"
      >
        {{ trafficStore.isCalculating ? 'Calculating…' : 'Calculate routes' }}
      </button>
      <div class="effects">
        <EffectRow label="Route the trips" :state="effectState" />
      </div>
      <div v-if="trafficStore.isCalculating" class="bc-empty calculate__msg">
        {{ loadingMessage }}
      </div>
      <div v-else-if="!trafficStore.areaReady" class="bc-empty calculate__msg">
        The server is still routing the trips of this area. You can calculate once it is done.
      </div>
      <div v-else-if="calculateError" class="bc-empty calculate__msg">
        {{ calculateError }}
      </div>
    </div>
  </StoryStep>

  <StoryStep
    :step="3"
    title="Results"
    :state="
      step === 'results'
        ? 'open'
        : step === 'scenario' && trafficStore.hasCalculatedRoutes
          ? 'done'
          : 'todo'
    "
    @open="scenarioStore.mapMode = 'result'"
  >
    <template #summary>{{ resultsSummary }}</template>
    <div v-if="trafficStore.isStale" class="stale-banner">
      Scenario changed since this result, shown at 40 % on the map.
      <button
        class="bc-micro stale-banner__btn"
        :disabled="trafficStore.isCalculating"
        @click="calculateRoutes"
      >
        {{ trafficStore.isCalculating ? 'Calculating…' : 'Calculate again' }}
      </button>
    </div>
    <div class="dock-section">
      <div class="bc-micro dock-section__title">
        Layers<template v-if="resultTrips"> · {{ resultTrips }} trips</template>
      </div>
      <LayerRows />

      <div v-if="hasBus" class="clip">
        <span class="clip__label">Clip to</span>
        <span
          class="clip__chip"
          :data-on="trafficStore.filterBusRoutes ? 'true' : 'false'"
          @click="trafficStore.filterBusRoutes = !trafficStore.filterBusRoutes"
          >Bus routes</span
        >
      </div>

      <!-- Where the diverted traffic ended up. These streets were not touched,
           they are what the result says. -->
      <template v-if="absorbers.length">
        <div class="bc-micro absorb-head">Where the traffic went · top 3</div>
        <div
          v-for="row in absorbers"
          :key="row.key"
          class="edge-row edge-row--absorb edge-row--click"
          :data-lit="scenarioStore.hoveredSet.has(row.key)"
          title="Zoom to this street"
          @click="focus(row.key)"
          @mouseenter="scenarioStore.hover({ keys: [row.key], dir: 'both' })"
          @mouseleave="scenarioStore.hover(null)"
        >
          <span class="edge-row__name">{{ row.name || 'Unnamed street' }}</span>
          <div class="edge-row__meta">
            <span class="edge-row__bar">
              <span
                class="edge-row__bar-fill"
                :style="{ width: barWidth(row.value), background: row.color }"
              ></span>
            </span>
            <span class="edge-row__delta">{{ deltaText(row.value) }}</span>
          </div>
        </div>
      </template>
    </div>

    <ImpactStatistics
      v-if="trafficStore.impactStatistics"
      :statistics="trafficStore.impactStatistics"
      :elastic-demand="trafficStore.elasticDemand"
    />
  </StoryStep>
</template>

<style scoped>
.stale-banner {
  margin: 16px 22px 0;
  padding: 8px 10px;
  border: 1px solid #b51f1f;
  color: #b51f1f;
  font-size: var(--bc-fs-small);
}

.stale-banner__btn {
  display: block;
  margin-top: 6px;
  padding: 0;
  background: none;
  border: 0;
  color: inherit;
  text-decoration: underline;
  cursor: pointer;
}

.stale-banner__btn:disabled {
  opacity: 0.5;
  cursor: default;
}

.dock-head {
  padding: 18px 22px 14px;
  border-bottom: 1px solid var(--bc-line);
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

.dock-section__title {
  margin-bottom: 8px;
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

.edge-row {
  display: grid;
  grid-template-columns: 34px 1fr auto 14px;
  gap: 10px;
  align-items: center;
  padding: 7px 0;
  border-top: 1px solid var(--bc-line);
  font-size: var(--bc-fs-body);
}

.edge-row--click {
  cursor: pointer;
}

.edge-row[data-lit='true'] {
  background: var(--bc-hover);
  box-shadow: -3px 0 0 0 var(--bc-accent);
}

/* absorbers carry no badge, so the name takes the whole first line */
.edge-row--absorb {
  grid-template-columns: 1fr;
}

/* the Δ bar goes on a second line, full width */
.edge-row__meta {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}

.edge-row__bar {
  flex: 1;
  height: 3px;
  background: var(--bc-line);
  min-width: 0;
}

.edge-row__bar-fill {
  display: block;
  height: 100%;
}

.edge-row__delta {
  font-family: var(--bc-font-mono);
  font-size: var(--bc-fs-micro);
  font-variant-numeric: tabular-nums;
  color: var(--bc-grey);
  white-space: nowrap;
}

.absorb-head {
  margin-top: 14px;
  margin-bottom: 2px;
}

.edge-row__badge {
  font-family: var(--bc-font-mono);
  font-size: var(--bc-fs-micro);
  letter-spacing: 0.04em;
  border: 1px solid var(--bc-ink);
  text-align: center;
  padding: 2px 0;
}

.edge-row__name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.edge-row__dir {
  font-family: var(--bc-font-mono);
  font-size: var(--bc-fs-micro);
  color: var(--bc-grey);
}

.edge-row__remove {
  background: none;
  border: 0;
  padding: 0;
  color: var(--bc-grey);
  cursor: pointer;
  display: flex;
}

.edge-row__remove:hover {
  color: var(--bc-ink);
}

.edit-graph {
  margin-top: 10px;
  width: 100%;
  font-family: var(--bc-font-mono);
  font-size: 10.5px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  background: transparent;
  color: var(--bc-ink);
  border: 1px solid var(--bc-ink);
  padding: 9px 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: background var(--bc-t);
}

.edit-graph:hover {
  background: var(--bc-hover);
}

.edit-graph__dot {
  width: 5px;
  height: 5px;
  background: var(--bc-accent);
  flex: none;
}

.edit-graph__dot[data-on='true'] {
  background: var(--bc-ink);
}

.edge-empty {
  margin: 8px 0 0;
}

.info-icon {
  display: flex;
  cursor: help;
}

.iterations {
  padding: 8px 0 4px 21px;
}

.iterations__label {
  font-size: var(--bc-fs-small);
  color: var(--bc-grey);
  margin-bottom: 2px;
}

.trips {
  margin-top: 14px;
}

.trips__label {
  margin-bottom: 6px;
}

/* no switching while a run is in flight, the answer would be for the old count */
.trips__seg--busy {
  opacity: 0.5;
  pointer-events: none;
}

.trips__warning {
  font-family: var(--bc-font-mono);
  font-size: var(--bc-fs-micro);
  line-height: 1.5;
  color: var(--bc-grey);
  margin: 6px 0 0;
}

.calculate {
  margin-top: 14px;
  width: 100%;
}

.calculate:disabled {
  opacity: 0.5;
  cursor: default;
}

.effects {
  margin-top: 10px;
}

.calculate__msg {
  margin-top: 6px;
}

.model-status {
  margin-top: 8px;
}

.clip {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: var(--bc-grey);
}

.clip__chip {
  font-family: var(--bc-font-mono);
  font-size: var(--bc-fs-micro);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  border: 1px solid var(--bc-ink);
  color: var(--bc-ink);
  padding: 3px 8px;
  cursor: pointer;
  transition:
    background var(--bc-t),
    color var(--bc-t);
}

.clip__chip[data-on='true'] {
  background: var(--bc-ink);
  color: var(--bc-ground);
}
</style>
