<script setup lang="ts">
import { ref, watch } from 'vue'
import { mdiChevronDown, mdiChevronRight } from '@mdi/js'
import { useCVRPStore } from '@/stores/cvrp'

const cvrpStore = useCVRPStore()
const isExpanded = ref(false)

watch(
  () => cvrpStore.lastResult,
  (val) => { if (val) isExpanded.value = true }
)
</script>

<template>
  <div v-if="cvrpStore.hasResult && cvrpStore.lastResult" class="cvrp-statistics">
    <div class="section-header" @click="isExpanded = !isExpanded">
      <div class="d-flex align-center">
        <v-btn
          :icon="isExpanded ? mdiChevronDown : mdiChevronRight"
          variant="text"
          density="compact"
          size="small"
        />
        <span class="section-title">SOLUTION SUMMARY</span>
      </div>
    </div>
    <v-expand-transition>
      <div v-show="isExpanded" class="section-content">
        <div class="stat-group">
          <div class="stat-row">
            <span class="stat-label">Routes:</span>
            <span class="stat-value">{{ cvrpStore.lastResult.n_routes }}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Centroids served:</span>
            <span class="stat-value">{{ cvrpStore.lastResult.centroids_used }}</span>
          </div>
          <div v-if="cvrpStore.lastResult.n_missing_clients > 0" class="stat-row">
            <span class="stat-label">Missing stops:</span>
            <span class="stat-value warning-value">{{ cvrpStore.lastResult.n_missing_clients }}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Total distance:</span>
            <span class="stat-value">{{ (cvrpStore.lastResult.total_distance_m / 1000).toFixed(1) }} km</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Solve time:</span>
            <span class="stat-value">{{ cvrpStore.lastResult.solve_time_ms.toFixed(0) }} ms</span>
          </div>
        </div>

        <!-- Visualization mode -->
        <div class="stat-group">
          <div class="stat-group-label">Display</div>
          <v-btn-toggle
            v-model="cvrpStore.visualizationMode"
            density="compact"
            variant="outlined"
            color="primary"
            mandatory
            class="mt-1"
          >
            <v-btn value="routes" size="small">Vehicle Routes</v-btn>
            <v-btn value="heatmap" size="small">Edge Load</v-btn>
          </v-btn-toggle>
        </div>
      </div>
    </v-expand-transition>
  </div>
</template>

<style scoped>
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  cursor: pointer;
  user-select: none;
}

.section-header:hover {
  background-color: rgba(var(--v-theme-on-surface), 0.05);
}

.section-title {
  font-size: 0.75rem;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.section-content {
  padding: 0 12px 8px 12px;
}

.stat-group {
  margin-bottom: 6px;
  padding-bottom: 6px;
  border-bottom: 1px solid #f0f0f0;
}

.stat-group:last-child {
  margin-bottom: 0;
  padding-bottom: 0;
  border-bottom: none;
}

.stat-group-label {
  font-size: 0.625rem;
  font-weight: 500;
  text-transform: uppercase;
  color: rgba(var(--v-theme-on-surface), 0.6);
  margin-bottom: 2px;
  letter-spacing: 0.5px;
}

.stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1px 0;
  font-size: 0.75rem;
}

.stat-label {
  color: rgba(var(--v-theme-on-surface), 0.7);
  font-weight: 400;
}

.stat-value {
  font-weight: 500;
  font-size: 0.8rem;
  color: rgb(var(--v-theme-on-surface));
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.warning-value {
  color: rgb(var(--v-theme-warning));
}
</style>
