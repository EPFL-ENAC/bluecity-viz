<script setup lang="ts">
import { computed, ref } from 'vue'
import { mdiChevronDown, mdiChevronRight } from '@mdi/js'

export interface ImpactStats {
  total_routes: number
  affected_routes: number
  failed_routes: number
  total_distance_increase_km: number
  total_time_increase_minutes: number
  avg_distance_increase_km: number
  avg_time_increase_minutes: number
  max_distance_increase_km: number
  max_time_increase_minutes: number
  avg_distance_increase_percent: number
  avg_time_increase_percent: number
  total_co2_increase_grams?: number
  avg_co2_increase_grams?: number
  max_co2_increase_grams?: number
  avg_co2_increase_percent?: number
}

interface Props {
  statistics: ImpactStats | null
}

const props = defineProps<Props>()

const isExpanded = ref(true)

const hasImpact = computed(() => {
  return props.statistics && props.statistics.affected_routes > 0
})

const affectedPercent = computed(() => {
  if (!props.statistics || props.statistics.total_routes === 0) return 0
  return ((props.statistics.affected_routes / props.statistics.total_routes) * 100).toFixed(1)
})

const hasFailedRoutes = computed(() => {
  return props.statistics && props.statistics.failed_routes > 0
})

function formatNumber(value: number, decimals: number = 2): string {
  return value.toFixed(decimals)
}
</script>

<template>
  <div v-if="statistics" class="impact-statistics">
    <div class="section-header" @click="isExpanded = !isExpanded">
      <div class="d-flex align-center">
        <v-btn
          :icon="isExpanded ? mdiChevronDown : mdiChevronRight"
          variant="text"
          density="compact"
          size="small"
        />
        <span class="section-title">IMPACT STATISTICS</span>
      </div>
    </div>
    <v-expand-transition>
      <div v-show="isExpanded" class="section-content">
        <!-- Overview -->
        <div class="stat-group">
          <div class="stat-row">
            <span class="stat-label">Total Routes:</span>
            <span class="stat-value">{{ statistics.total_routes }}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Affected:</span>
            <span class="stat-value">
              {{ statistics.affected_routes }} ({{ affectedPercent }}%)
            </span>
          </div>
          <div v-if="hasFailedRoutes" class="stat-row">
            <span class="stat-label">Failed:</span>
            <span class="stat-value">{{ statistics.failed_routes }}</span>
          </div>
        </div>

        <!-- Total Impact -->
        <div v-if="hasImpact" class="stat-group">
          <div class="stat-group-label">Total Impact</div>
          <div class="stat-row">
            <span class="stat-label">Distance:</span>
            <span class="stat-value"
              >+{{ formatNumber(statistics.total_distance_increase_km, 2) }} km</span
            >
          </div>
          <div class="stat-row">
            <span class="stat-label">Time:</span>
            <span class="stat-value"
              >+{{ formatNumber(statistics.total_time_increase_minutes, 1) }} min</span
            >
          </div>
          <div v-if="statistics.total_co2_increase_grams !== undefined" class="stat-row">
            <span class="stat-label">CO₂:</span>
            <span class="stat-value"
              >+{{ formatNumber(statistics.total_co2_increase_grams / 1000, 2) }} kg</span
            >
          </div>
        </div>

        <!-- Average Impact -->
        <div v-if="hasImpact" class="stat-group">
          <div class="stat-group-label">Average (per affected)</div>
          <div class="stat-row">
            <span class="stat-label">Distance:</span>
            <span class="stat-value">
              +{{ formatNumber(statistics.avg_distance_increase_km, 2) }} km
              <span class="stat-secondary"
                >({{ formatNumber(statistics.avg_distance_increase_percent, 1) }}%)</span
              >
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Time:</span>
            <span class="stat-value">
              +{{ formatNumber(statistics.avg_time_increase_minutes, 1) }} min
              <span class="stat-secondary"
                >({{ formatNumber(statistics.avg_time_increase_percent, 1) }}%)</span
              >
            </span>
          </div>
          <div v-if="statistics.avg_co2_increase_grams !== undefined" class="stat-row">
            <span class="stat-label">CO₂:</span>
            <span class="stat-value">
              +{{ formatNumber(statistics.avg_co2_increase_grams, 0) }} g
              <span class="stat-secondary"
                >({{ formatNumber(statistics.avg_co2_increase_percent ?? 0, 1) }}%)</span
              >
            </span>
          </div>
        </div>

        <!-- Maximum Impact -->
        <div v-if="hasImpact" class="stat-group">
          <div class="stat-group-label">Maximum (worst case)</div>
          <div class="stat-row">
            <span class="stat-label">Distance:</span>
            <span class="stat-value"
              >+{{ formatNumber(statistics.max_distance_increase_km, 2) }} km</span
            >
          </div>
          <div class="stat-row">
            <span class="stat-label">Time:</span>
            <span class="stat-value"
              >+{{ formatNumber(statistics.max_time_increase_minutes, 1) }} min</span
            >
          </div>
          <div v-if="statistics.max_co2_increase_grams !== undefined" class="stat-row">
            <span class="stat-label">CO₂:</span>
            <span class="stat-value"
              >+{{ formatNumber(statistics.max_co2_increase_grams, 0) }} g</span
            >
          </div>
        </div>

        <!-- No impact message -->
        <div v-if="!hasImpact && statistics.affected_routes === 0" class="text-center py-2">
          <span class="text-caption text-medium-emphasis">No routes affected</span>
        </div>
      </div>
    </v-expand-transition>
  </div>
</template>

<style scoped>
.impact-statistics {
  border-bottom: 1px solid #e0e0e0;
}

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
  color: rgb(var(--v-theme-on-surface));
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.stat-secondary {
  font-size: 0.688rem;
  color: rgba(var(--v-theme-on-surface), 0.5);
  margin-left: 4px;
  font-weight: 400;
}
</style>
