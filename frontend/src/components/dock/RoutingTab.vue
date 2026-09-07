<script setup lang="ts">
import ImpactStatistics from '@/components/ImpactStatistics.vue'
import BcIcon from '@/components/ui/BcIcon.vue'
import BcRow from '@/components/ui/BcRow.vue'
import BcSeg from '@/components/ui/BcSeg.vue'
import BcSlider from '@/components/ui/BcSlider.vue'
import { recalculateRoutes } from '@/services/trafficAnalysis'
import { useScenarioStore } from '@/stores/scenario'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { computed, onMounted, ref } from 'vue'

// The routing tool, inside the scenario workbench. The scenario itself (the
// modified edges) belongs to the dock above, both tools read it.

const trafficStore = useTrafficAnalysisStore()
const scenarioStore = useScenarioStore()

const loadingMessage = ref('')

// The pair counts come from the server, not from a constant here.
onMounted(() => {
  trafficStore.loadGraphInfo().catch((error) => {
    console.error('Failed to load graph info:', error)
  })
})

function formatTrips(count: number): string {
  return count.toLocaleString('en-US')
}

// The two choices, hidden until we know the numbers.
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

// Sentence-case labels, per the design. Falls back to the store label.
const VIS_LABELS: Record<string, string> = {
  frequency: 'Edge usage frequency',
  co2: 'CO₂ emissions',
  delta: 'Traffic change (Δ)',
  delta_relative: 'Traffic change (Δ, relative %)',
  co2_delta: 'CO₂ emissions change',
  betweenness: 'Betweenness centrality',
  betweenness_delta: 'Betweenness change'
}

function visLabel(mode: string, fallback: string) {
  return VIS_LABELS[mode] ?? fallback
}

async function calculateRoutes() {
  const odPairs = chosenOdPairs()
  const trips = odPairs ? ` on ${formatTrips(odPairs)} trips` : ''

  trafficStore.isCalculating = true
  loadingMessage.value = trafficStore.useCongestionModel
    ? `Congestion routing (${trafficStore.congestionIterations} iteration${
        trafficStore.congestionIterations > 1 ? 's' : ''
      })${trips}…`
    : `Calculating routes${trips}…`
  try {
    // The baseline is the same for every run at that count, so it comes from
    // the store cache after the first time.
    const [baseline, result] = await Promise.all([
      trafficStore.getBaseline(odPairs),
      recalculateRoutes(scenarioStore.wire, {
        useCongestionModel: trafficStore.useCongestionModel,
        congestionIterations: trafficStore.congestionIterations,
        elasticDemand: trafficStore.elasticDemand,
        odPairs
      })
    ])

    // The count changed while we were waiting, this answer is for the old one.
    if (odPairs !== chosenOdPairs()) return

    if (baseline.odPairs !== result.od_pairs) {
      console.warn(`Baseline is on ${baseline.odPairs} pairs, the run on ${result.od_pairs}`)
    }

    trafficStore.setEdgeUsage(
      baseline.rows,
      result.new_edge_usage,
      result.impact_statistics,
      result.od_pairs,
      scenarioStore.hash
    )
  } catch (error) {
    console.error('Failed to calculate routes:', error)
  } finally {
    trafficStore.isCalculating = false
  }
}
</script>

<template>
  <div>

    <p v-if="trafficStore.isStale" class="stale-banner">
      Scenario changed since this result, shown at 40 % on the map.
    </p>
    <!-- Routing model -->
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
                <strong>Off (static betweenness):</strong> BC is computed once on the modified graph
                to derive congested travel times (<em>duration_bc</em>), then all affected routes
                are re-run with those weights. Roads that structurally attract more flow appear
                slower, discouraging over-assignment without any iteration.
              </div>
              <div>
                <strong>On (iterative volumes):</strong> actual simulated route volumes are counted,
                normalised to daily vehicle-km, and fed into the BPR speed-reduction formula. Routes
                are then re-run with the updated weights, repeating for the chosen number of
                iterations, converging toward a <em>Wardrop user equilibrium</em>.
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
                When on, trip destinations are resampled to reflect that travellers adapt to new
                travel times. Closing a major road shifts trips to closer destinations rather than
                spiking total travel time. Origins remain unchanged; only destination choice
                responds to the modified network.
              </div>
            </div>
          </v-tooltip>
        </template>
      </BcRow>

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

      <button
        class="bc-btn bc-btn--primary calculate"
        :disabled="trafficStore.isCalculating"
        @click="calculateRoutes"
      >
        {{ trafficStore.isCalculating ? 'Calculating…' : 'Calculate routes' }}
      </button>
      <v-progress-linear
        v-if="trafficStore.isCalculating"
        class="calculate__progress"
        color="secondary"
        :height="1"
        indeterminate
      />
      <div v-if="trafficStore.isCalculating" class="bc-empty calculate__msg">
        {{ loadingMessage }}
      </div>
    </div>

    <!-- Visualisation -->
    <div v-if="trafficStore.hasCalculatedRoutes" class="dock-section">
      <div class="bc-micro dock-section__title">
        Visualisation<template v-if="resultTrips"> · {{ resultTrips }} trips</template>
      </div>
      <BcRow
        v-for="vis in trafficStore.availableVisualizations"
        :key="vis.value"
        :check="false"
        :on="trafficStore.activeVisualization === vis.value"
        :active="trafficStore.activeVisualization === vis.value"
        class="vis-row"
        @click="trafficStore.setActiveVisualization(vis.value)"
      >
        {{ visLabel(vis.value, vis.label) }}
      </BcRow>

      <div class="clip">
        <span class="clip__label">Clip to</span>
        <span
          class="clip__chip"
          :data-on="trafficStore.filterBusRoutes ? 'true' : 'false'"
          @click="trafficStore.filterBusRoutes = !trafficStore.filterBusRoutes"
          >Bus routes</span
        >
      </div>
    </div>

    <!-- Impact -->
    <ImpactStatistics
      v-if="trafficStore.impactStatistics"
      :statistics="trafficStore.impactStatistics"
      :elastic-demand="trafficStore.elasticDemand"
    />
  </div>
</template>

<style scoped>
.stale-banner {
  margin: 16px 22px 0;
  padding: 8px 10px;
  border: 1px solid #b51f1f;
  color: #b51f1f;
  font-size: var(--bc-fs-small);
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

.calculate__progress {
  margin-top: 8px;
}

.calculate__msg {
  margin-top: 6px;
}

.vis-row {
  padding-left: 12px;
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
