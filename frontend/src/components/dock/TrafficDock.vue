<script setup lang="ts">
import { computed, ref } from 'vue'
import { useLayersStore } from '@/stores/layers'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { recalculateRoutes } from '@/services/trafficAnalysis'
import ImpactStatistics from '@/components/ImpactStatistics.vue'
import BcIcon from '@/components/ui/BcIcon.vue'
import BcRow from '@/components/ui/BcRow.vue'
import BcSlider from '@/components/ui/BcSlider.vue'

const layersStore = useLayersStore()
const trafficStore = useTrafficAnalysisStore()

const loadingMessage = ref('')

const title = computed(() => layersStore.activeInvestigation?.name ?? 'Road closure scenario')

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

// The badge in front of each modified edge: x to remove, else the speed limit.
function edgeBadge(action: string) {
  if (action === 'remove') return '×'
  if (action === 'speed10') return '10'
  if (action === 'speed30') return '30'
  return '50'
}

async function calculateRoutes() {
  trafficStore.isCalculating = true
  loadingMessage.value = trafficStore.useCongestionModel
    ? `Congestion routing (${trafficStore.congestionIterations} iteration${
        trafficStore.congestionIterations > 1 ? 's' : ''
      })…`
    : 'Calculating routes…'
  try {
    const result = await recalculateRoutes(trafficStore.edgeModificationsArray, {
      useCongestionModel: trafficStore.useCongestionModel,
      congestionIterations: trafficStore.congestionIterations,
      elasticDemand: trafficStore.elasticDemand
    })
    trafficStore.setEdgeUsage(
      result.original_edge_usage,
      result.new_edge_usage,
      result.impact_statistics
    )
  } catch (error) {
    console.error('Failed to calculate routes:', error)
  } finally {
    trafficStore.isCalculating = false
  }
}
</script>

<template>
  <div class="dock-panel">
    <div class="dock-head">
      <div class="bc-micro">Traffic analysis</div>
      <div class="dock-title">{{ title }}</div>
    </div>

    <!-- Modified edges -->
    <div class="dock-section">
      <div class="dock-section__head">
        <span class="bc-micro">Modified edges · {{ trafficStore.edgeModificationsCount }}</span>
        <button
          v-if="trafficStore.edgeModificationsCount > 0"
          class="bc-micro clear-btn"
          @click="trafficStore.clearEdgeModifications()"
        >
          Clear
        </button>
      </div>

      <div
        v-for="edge in trafficStore.edgeModificationsForDisplay"
        :key="`${edge.u}-${edge.v}`"
        class="edge-row"
      >
        <span class="edge-row__badge">{{ edgeBadge(edge.action) }}</span>
        <span class="edge-row__name">{{ edge.name }}</span>
        <span class="edge-row__dir">{{ edge.isBidirectional ? '↔' : '→' }}</span>
        <button
          class="edge-row__remove"
          title="Remove this modification"
          @click="trafficStore.removeEdgeModification(edge.u, edge.v)"
        >
          <BcIcon name="x" />
        </button>
      </div>

      <p v-if="trafficStore.edgeModificationsCount === 0" class="bc-empty edge-empty">
        Click an edge on the map to cycle: remove → 50 → 30 → 10 km/h.
      </p>
    </div>

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
                <strong>Off — Static betweenness:</strong> BC is computed once on the modified graph
                to derive congested travel times (<em>duration_bc</em>), then all affected routes
                are re-run with those weights. Roads that structurally attract more flow appear
                slower, discouraging over-assignment without any iteration.
              </div>
              <div>
                <strong>On — Iterative volumes:</strong> actual simulated route volumes are counted,
                normalised to daily vehicle-km, and fed into the BPR speed-reduction formula. Routes
                are then re-run with the updated weights, repeating for the chosen number of
                iterations — converging toward a <em>Wardrop user equilibrium</em>.
              </div>
            </div>
          </v-tooltip>
        </template>
      </BcRow>

      <div v-if="trafficStore.useCongestionModel" class="iterations">
        <div class="iterations__label">
          Iterations ({{ trafficStore.congestionIterations }}) — ~{{
            trafficStore.congestionIterations * 10
          }}s
        </div>
        <BcSlider v-model="trafficStore.congestionIterations" :min="1" :max="5" :step="1" />
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
      <div class="bc-micro dock-section__title">Visualisation</div>
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
  transition: background var(--bc-t), color var(--bc-t);
}

.clip__chip[data-on='true'] {
  background: var(--bc-ink);
  color: var(--bc-ground);
}
</style>
