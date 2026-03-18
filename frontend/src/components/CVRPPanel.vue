<script setup lang="ts">
import { ref } from 'vue'
import { useCVRPStore } from '@/stores/cvrp'
import {
  mdiChevronDown,
  mdiChevronRight,
  mdiTruck,
  mdiMapMarker,
  mdiClose,
} from '@mdi/js'

const cvrpStore = useCVRPStore()
const expanded = ref(false)
const errorMessage = ref('')

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

const wasteTypeOptions = [
  { value: 'DI', label: 'DI — Incinerable' },
  { value: 'DV', label: 'DV — Vegetable' },
  { value: 'PC', label: 'PC — Paper/Cardboard' },
  { value: 'VE', label: 'VE — Glass' },
]

const loadUnitOptions = [
  { value: 'kg', label: 'kg' },
  { value: 'kg_m', label: 'kg·m' },
]

</script>

<template>
  <div class="control-section">
    <div class="section-header" @click="expanded = !expanded">
      <div class="d-flex align-center flex-grow-1">
        <v-btn
          :icon="expanded ? mdiChevronDown : mdiChevronRight"
          variant="text"
          density="compact"
          size="small"
        />
        <span class="section-title">WASTE COLLECTION</span>
      </div>
    </div>

    <v-expand-transition>
      <div v-show="expanded" class="section-content">
        <!-- Waste type -->
        <v-select
          v-model="cvrpStore.wasteType"
          :items="wasteTypeOptions"
          item-title="label"
          item-value="value"
          label="Waste type"
          density="compact"
          variant="outlined"
          hide-details
          class="mb-3"
        />

        <!-- Vehicles -->
        <div class="text-caption text-medium-emphasis mb-1">
          Vehicles ({{ cvrpStore.nVehicles }})
        </div>
        <v-slider
          v-model="cvrpStore.nVehicles"
          :min="1"
          :max="20"
          :step="1"
          hide-details
          density="compact"
          color="primary"
          thumb-label
          class="mb-3"
        />

        <!-- Vehicle capacity -->
        <div class="text-caption text-medium-emphasis mb-1">
          Capacity kg ({{ cvrpStore.vehicleCapacity.toLocaleString() }})
        </div>
        <v-slider
          v-model="cvrpStore.vehicleCapacity"
          :min="500"
          :max="20000"
          :step="500"
          hide-details
          density="compact"
          color="primary"
          thumb-label
          class="mb-3"
        />

        <!-- Max runtime -->
        <div class="text-caption text-medium-emphasis mb-1">
          Solver time limit ({{ cvrpStore.maxRuntime }}s)
        </div>
        <v-slider
          v-model="cvrpStore.maxRuntime"
          :min="2"
          :max="60"
          :step="1"
          hide-details
          density="compact"
          color="primary"
          thumb-label
          class="mb-3"
        />

        <!-- Load unit -->
        <v-btn-toggle
          v-model="cvrpStore.loadUnit"
          density="compact"
          variant="outlined"
          color="primary"
          class="mb-3"
          mandatory
        >
          <v-btn
            v-for="opt in loadUnitOptions"
            :key="opt.value"
            :value="opt.value"
            size="small"
          >
            {{ opt.label }}
          </v-btn>
        </v-btn-toggle>

        <!-- Action buttons -->
        <div class="d-flex gap-2 mb-2">
          <v-btn
            variant="outlined"
            size="small"
            :prepend-icon="mdiMapMarker"
            :loading="false"
            @click="handleLoadCentroids"
          >
            Show Points
          </v-btn>
          <v-btn
            variant="outlined"
            size="small"
            :prepend-icon="mdiTruck"
            :loading="cvrpStore.isSolving"
            :disabled="cvrpStore.isSolving"
            color="primary"
            @click="handleSolve"
          >
            Solve
          </v-btn>
          <v-btn
            v-if="cvrpStore.hasResult"
            variant="text"
            size="small"
            :icon="mdiClose"
            @click="handleClear"
          />
        </div>

        <!-- Progress -->
        <v-progress-linear v-if="cvrpStore.isSolving" indeterminate class="mb-2" />

        <!-- Error -->
        <v-alert
          v-if="errorMessage"
          type="error"
          density="compact"
          variant="tonal"
          class="mb-2 text-caption"
        >
          {{ errorMessage }}
        </v-alert>

      </div>
    </v-expand-transition>
  </div>
</template>

<style scoped>
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  cursor: pointer;
  user-select: none;
  border-bottom: 1px solid #e0e0e0;
}

.section-header:hover {
  background-color: rgba(var(--v-theme-on-surface), 0.05);
}

.section-title {
  font-size: 0.875rem;
  font-weight: 500;
  text-transform: uppercase;
}

.section-content {
  padding: 12px 16px 16px 16px;
}

.result-summary {
  background-color: rgba(var(--v-theme-surface-variant), 0.5);
  border-radius: 4px;
  padding: 8px;
}

.result-grid {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 2px 8px;
}

.gap-2 {
  gap: 8px;
}
</style>
