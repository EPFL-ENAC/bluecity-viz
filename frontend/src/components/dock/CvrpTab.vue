<script setup lang="ts">
import BcIcon from '@/components/ui/BcIcon.vue'
import BcSeg from '@/components/ui/BcSeg.vue'
import BcSlider from '@/components/ui/BcSlider.vue'
import { useCVRPStore } from '@/stores/cvrp'
import { routeSummaries } from '@/utils/cvrpSource'
import { computed, ref } from 'vue'

// The waste collection tool, inside the scenario workbench.

const cvrpStore = useCVRPStore()
const errorMessage = ref('')

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

const emit = defineEmits<{ (event: 'hover-route', routeId: number | null): void }>()

// thousands separator with a plain space, like the design ("8 000 kg")
const capacityDisplay = computed(
  () => `${String(cvrpStore.vehicleCapacity).replace(/\B(?=(\d{3})+(?!\d))/g, ' ')} kg`
)

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

async function handleLoadCentroids() {
  errorMessage.value = ''
  try {
    await cvrpStore.loadCentroids()
  } catch (err: any) {
    errorMessage.value = err?.message ?? 'Failed to load centroids'
  }
}

function handleClear() {
  cvrpStore.clearResult()
  cvrpStore.showCentroids = false
  cvrpStore.centroids = null
  errorMessage.value = ''
}
</script>
<template>
  <div>
    <p v-if="cvrpStore.isStale" class="stale-banner">
      Scenario changed since this result, shown at 40 % on the map.
    </p>
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

      <div class="actions">
        <button class="bc-btn actions__btn" @click="handleLoadCentroids">Show points</button>
        <button
          class="bc-btn bc-btn--primary actions__btn"
          :disabled="cvrpStore.isSolving"
          @click="handleSolve"
        >
          {{ cvrpStore.isSolving ? 'Solving…' : 'Solve' }}
        </button>
      </div>
      <v-progress-linear
        v-if="cvrpStore.isSolving"
        class="actions__progress"
        color="secondary"
        :height="1"
        indeterminate
      />
      <p v-if="errorMessage" class="error-msg">{{ errorMessage }}</p>
    </div>

    <div v-if="cvrpStore.hasResult && cvrpStore.lastResult" class="dock-section">
      <div class="section-head">
        <span class="bc-micro">Solution</span>
        <button class="icon-btn" title="Clear result" @click="handleClear">
          <BcIcon name="x" />
        </button>
      </div>

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

      <div class="row">
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
  </div>
</template>

<style scoped>
.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.stale-banner {
  margin: 16px 22px 0;
  padding: 8px 10px;
  border: 1px solid #b51f1f;
  color: #b51f1f;
  font-size: var(--bc-fs-small);
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

.actions {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}

.actions__btn {
  flex: 1;
}

.actions__btn:disabled {
  opacity: 0.5;
  cursor: default;
}

.actions__progress {
  margin-top: 8px;
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

.icon-btn {
  background: none;
  border: 0;
  padding: 0;
  color: var(--bc-grey);
  cursor: pointer;
  display: flex;
}

.icon-btn:hover {
  color: var(--bc-ink);
}
</style>
