<script setup lang="ts">
import EffectRow, { type EffectState } from '@/components/dock/EffectRow.vue'
import ScenarioEdges from '@/components/dock/ScenarioEdges.vue'
import StoryStep from '@/components/dock/StoryStep.vue'
import BcRow from '@/components/ui/BcRow.vue'
import BcSeg from '@/components/ui/BcSeg.vue'
import BcSlider from '@/components/ui/BcSlider.vue'
import { useMapView } from '@/composables/useMapView'
import { useCVRPStore } from '@/stores/cvrp'
import { useScenarioStore, type StreetRef } from '@/stores/scenario'
import { useStorylineStore } from '@/stores/storyline'
import { routeSummaries } from '@/utils/cvrpSource'
import { computed, ref } from 'vue'

// The waste collection tool as one storyline of three steps: set the fleet,
// edit the network and plan the rounds, then read the map and the numbers. The
// modified edges are shared with the routing tool.

const cvrpStore = useCVRPStore()
const scenarioStore = useScenarioStore()
const storyline = useStorylineStore()
const errorMessage = ref('')

const { step } = useMapView()

/** The wheel while the solver runs, the tick once the rounds match the scenario. */
const effectState = computed<EffectState>(() => {
  if (cvrpStore.isSolving) return 'running'
  if (cvrpStore.hasResult && !cvrpStore.isStale) return 'done'
  return 'idle'
})

const wasteTypeOptions = [
  { value: 'DI', label: 'DI' },
  { value: 'DV', label: 'DV' },
  { value: 'PC', label: 'PC' },
  { value: 'VE', label: 'VE' }
]

const loadUnitOptions = [
  { value: 'kg', label: 'kg' },
  { value: 'kg_m', label: 'kg·m' }
]

const displayOptions = [
  { value: 'routes', label: 'Routes' },
  { value: 'heatmap', label: 'Edge load' }
]

// One row per vehicle: hue, trips, load, distance.
const routes = computed(() =>
  cvrpStore.lastResult ? routeSummaries(cvrpStore.lastResult.route_segments) : []
)

const emit = defineEmits<{
  (event: 'hover-route', routeId: number | null): void
  (event: 'focus', keys: string[], select?: StreetRef): void
}>()

// thousands separator with a plain space, like the design ("8 000 kg")
const capacityDisplay = computed(
  () => `${String(cvrpStore.vehicleCapacity).replace(/\B(?=(\d{3})+(?!\d))/g, ' ')} kg`
)

/** The fleet in one line, for the folded Model step. */
const modelSummary = computed(
  () =>
    `${cvrpStore.wasteType} · ${cvrpStore.nVehicles} vehicle${cvrpStore.nVehicles > 1 ? 's' : ''} · ${capacityDisplay.value} · ${cvrpStore.maxRuntime} s limit`
)

const scenarioSummary = computed(() => {
  const n = scenarioStore.count
  const edges = n === 0 ? 'No street modified' : `${n} street${n > 1 ? 's' : ''} modified`
  if (step.value === 'model') return `${edges}. Validate the model to edit the network.`
  return cvrpStore.isStale ? `${edges}, changed since the result` : edges
})

const resultsSummary = computed(() => {
  if (step.value === 'model') return 'Shown once the rounds are calculated.'
  const result = cvrpStore.lastResult
  if (!result) return 'Calculate the rounds to see them.'
  const km = (result.total_distance_m / 1000).toFixed(1)
  return `${result.n_routes} route${result.n_routes > 1 ? 's' : ''} · ${km} km`
})

async function handleSolve() {
  errorMessage.value = ''
  try {
    await cvrpStore.solve()
    // Default to routes visualization after solving
    cvrpStore.visualizationMode = 'routes'
  } catch (err: any) {
    errorMessage.value = err?.message ?? 'Solve failed'
  }
}

/**
 * The collection points are a base layer: they can be shown before any run.
 * They are fetched once per waste type, then only shown or hidden.
 */
async function toggleCentroids() {
  errorMessage.value = ''
  if (cvrpStore.showCentroids) {
    cvrpStore.showCentroids = false
    return
  }
  if (cvrpStore.centroids) {
    cvrpStore.showCentroids = true
    return
  }
  try {
    await cvrpStore.loadCentroids()
  } catch (err: any) {
    errorMessage.value = err?.message ?? 'Failed to load centroids'
  }
}
</script>

<template>
  <StoryStep
    :step="1"
    title="Model"
    :state="step === 'model' ? 'open' : 'done'"
    action="Edit"
    :busy="cvrpStore.isSolving"
    @open="storyline.returnToInit('cvrp')"
  >
    <template #summary>
      {{ modelSummary
      }}<template v-if="cvrpStore.hasResult">. Editing it drops the result.</template>
    </template>
    <div class="dock-section">
      <div class="bc-micro dock-section__title">Waste type</div>
      <BcSeg v-model="cvrpStore.wasteType" :options="wasteTypeOptions" equal />

      <BcSlider
        v-model="cvrpStore.nVehicles"
        class="param"
        label="Vehicles"
        :min="1"
        :max="20"
        :step="1"
      />
      <BcSlider
        v-model="cvrpStore.vehicleCapacity"
        class="param"
        label="Capacity"
        :min="500"
        :max="20000"
        :step="500"
        :display="capacityDisplay"
      />
      <BcSlider
        v-model="cvrpStore.maxRuntime"
        class="param"
        label="Solver time limit"
        :min="2"
        :max="60"
        :step="1"
        :display="`${cvrpStore.maxRuntime} s`"
      />

      <div class="row">
        <span class="row__label">Load unit</span>
        <BcSeg v-model="cvrpStore.loadUnit" :options="loadUnitOptions" />
      </div>
    </div>

    <!-- The collection points are a base layer: they can be looked at while the
         fleet is set, before any run. -->
    <div class="dock-section">
      <div class="bc-micro dock-section__title">Map</div>
      <BcRow :on="cvrpStore.showCentroids" @click="toggleCentroids">Collection points</BcRow>
      <p v-if="errorMessage" class="error-msg">{{ errorMessage }}</p>

      <button class="bc-btn bc-btn--primary validate" @click="storyline.validate('cvrp')">
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
    <p v-if="cvrpStore.isStale" class="stale-banner">
      Scenario changed since the last result. Calculate again to update it.
    </p>
    <div class="dock-section">
      <ScenarioEdges @focus="(keys, select) => emit('focus', keys, select)" />

      <button
        class="bc-btn bc-btn--primary actions__btn"
        :disabled="cvrpStore.isSolving"
        @click="handleSolve"
      >
        {{ cvrpStore.isSolving ? 'Calculating…' : 'Calculate rounds' }}
      </button>
      <div class="effects">
        <EffectRow label="Plan the rounds" :state="effectState" />
      </div>
      <p v-if="errorMessage" class="error-msg">{{ errorMessage }}</p>
    </div>
  </StoryStep>

  <StoryStep
    :step="3"
    title="Results"
    :state="
      step === 'results' ? 'open' : step === 'scenario' && cvrpStore.hasResult ? 'done' : 'todo'
    "
    @open="scenarioStore.mapMode = 'result'"
  >
    <template #summary>{{ resultsSummary }}</template>
    <div v-if="cvrpStore.isStale" class="stale-banner">
      Scenario changed since this result, shown at 40 % on the map.
      <button
        class="bc-micro stale-banner__btn"
        :disabled="cvrpStore.isSolving"
        @click="handleSolve"
      >
        {{ cvrpStore.isSolving ? 'Calculating…' : 'Calculate again' }}
      </button>
    </div>
    <div class="dock-section">
      <div class="bc-micro dock-section__title">Layers</div>
      <BcRow :on="cvrpStore.showCentroids" @click="toggleCentroids">Collection points</BcRow>

      <div v-if="cvrpStore.hasResult" class="row">
        <span class="row__label">Display</span>
        <BcSeg v-model="cvrpStore.visualizationMode" :options="displayOptions" />
      </div>
    </div>

    <div v-if="routes.length" class="dock-section">
      <div class="bc-micro dock-section__title">Vehicles</div>
      <div
        v-for="route in routes"
        :key="route.route_id"
        class="veh"
        @mouseenter="emit('hover-route', route.route_id)"
        @mouseleave="emit('hover-route', null)"
      >
        <span class="veh__hue" :style="{ background: route.color }"></span>
        <span class="veh__id">{{ route.route_id + 1 }}</span>
        <span class="veh__trips">{{ route.trips }} trip{{ route.trips > 1 ? 's' : '' }}</span>
        <span class="veh__num">{{ Math.round(route.load_kg).toLocaleString('en-US') }} kg</span>
        <span class="veh__num">{{ (route.distance_m / 1000).toFixed(1) }} km</span>
      </div>
    </div>

    <div v-if="cvrpStore.lastResult" class="dock-section">
      <div class="bc-micro dock-section__title">Solution</div>
      <div class="kv">
        <span class="kv__key">Routes</span>
        <span>{{ cvrpStore.lastResult.n_routes }}</span>
      </div>
      <div class="kv">
        <span class="kv__key">Centroids served</span>
        <span>{{ cvrpStore.lastResult.centroids_used }}</span>
      </div>
      <div v-if="cvrpStore.lastResult.n_missing_clients > 0" class="kv">
        <span class="kv__key">Missing stops</span>
        <span class="kv__danger">{{ cvrpStore.lastResult.n_missing_clients }}</span>
      </div>
      <div class="kv">
        <span class="kv__key">Total distance</span>
        <span>{{ (cvrpStore.lastResult.total_distance_m / 1000).toFixed(1) }} km</span>
      </div>
      <div class="kv">
        <span class="kv__key">Solve time</span>
        <span>{{ (cvrpStore.lastResult.solve_time_ms / 1000).toFixed(1) }} s</span>
      </div>
    </div>
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

/* one row per vehicle: hue, number, trips, load, distance */
.veh {
  display: grid;
  grid-template-columns: 16px 28px 1fr auto auto;
  gap: 10px;
  align-items: center;
  padding: 6px 0;
  border-top: 1px solid var(--bc-line);
  font-size: var(--bc-fs-body);
  cursor: default;
}

.veh:hover {
  background: var(--bc-hover);
}

.veh__hue {
  height: 3px;
}

.veh__id {
  font-family: var(--bc-font-mono);
  font-size: var(--bc-fs-micro);
  color: var(--bc-grey);
}

.veh__trips {
  color: var(--bc-grey);
  font-size: var(--bc-fs-small);
}

.veh__num {
  font-variant-numeric: tabular-nums;
  font-size: 12.5px;
}

.dock-head {
  padding: 18px 22px 14px;
  border-bottom: 1px solid var(--bc-line);
}

.dock-head__title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
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

.dock-section__title {
  margin-bottom: 8px;
}

.param {
  margin-top: 16px;
}

.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 16px;
  font-size: var(--bc-fs-body);
}

.row__label {
  color: var(--bc-grey);
}

.validate,
.actions__btn {
  width: 100%;
  margin-top: 16px;
}

.actions__btn:disabled {
  opacity: 0.5;
  cursor: default;
}

.effects {
  margin-top: 10px;
}

.error-msg {
  margin: 8px 0 0;
  font-size: var(--bc-fs-small);
  color: var(--bc-danger);
}

.kv {
  display: flex;
  justify-content: space-between;
  padding: 5px 0;
  border-top: 1px solid var(--bc-line);
  font-size: var(--bc-fs-body);
  font-variant-numeric: tabular-nums;
}

.kv__key {
  color: var(--bc-grey);
}

.kv__danger {
  color: var(--bc-danger);
}
</style>
