<script setup lang="ts">
import { formatCo2, formatCount, formatDistance, formatTime } from '@/utils/impactFormat'
import { computed } from 'vue'

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
  elasticDemand?: boolean
}

const props = withDefaults(defineProps<Props>(), { elasticDemand: false })

const header = computed(() => {
  const s = props.statistics
  if (!s) return 'Impact'
  // with elastic demand every trip is drawn again, so only the totals make sense
  if (props.elasticDemand) return `Impact · ${formatCount(s.total_routes)} trips`
  const share = s.total_routes > 0 ? (s.affected_routes / s.total_routes) * 100 : 0
  const percent = share >= 10 ? share.toFixed(0) : share.toFixed(1)
  return `Impact · ${formatCount(s.affected_routes)} of ${formatCount(s.total_routes)} affected (${percent}%)`
})

// One row per measure, with the three columns of the design.
const rows = computed(() => {
  const s = props.statistics
  if (!s) return []
  return [
    {
      key: 'Distance',
      total: formatDistance(s.total_distance_increase_km),
      avg: formatDistance(s.avg_distance_increase_km),
      max: formatDistance(s.max_distance_increase_km)
    },
    {
      key: 'Time',
      total: formatTime(s.total_time_increase_minutes),
      avg: formatTime(s.avg_time_increase_minutes),
      max: formatTime(s.max_time_increase_minutes)
    },
    {
      key: 'CO₂',
      total: formatCo2(s.total_co2_increase_grams),
      avg: formatCo2(s.avg_co2_increase_grams),
      max: formatCo2(s.max_co2_increase_grams)
    }
  ]
})
</script>

<template>
  <div v-if="statistics" class="impact">
    <div class="bc-micro impact__head">{{ header }}</div>

    <div class="impact__table" :class="{ 'impact__table--total-only': elasticDemand }">
      <span />
      <span class="impact__col">Total</span>
      <template v-if="!elasticDemand">
        <span class="impact__col">Avg</span>
        <span class="impact__col">Max</span>
      </template>

      <template v-for="row in rows" :key="row.key">
        <span class="impact__label">{{ row.key }}</span>
        <span class="impact__value">{{ row.total }}</span>
        <template v-if="!elasticDemand">
          <span class="impact__value">{{ row.avg }}</span>
          <span class="impact__value impact__value--max">{{ row.max }}</span>
        </template>
      </template>

      <template v-if="statistics.failed_routes > 0">
        <span class="impact__label impact__label--danger">Failed</span>
        <span class="impact__value impact__value--danger">{{ statistics.failed_routes }}</span>
        <template v-if="!elasticDemand">
          <span class="impact__value" />
          <span class="impact__value" />
        </template>
      </template>
    </div>
  </div>
</template>

<style scoped>
.impact {
  padding: 16px 22px 22px;
}

.impact__head {
  margin-bottom: 10px;
}

.impact__table {
  display: grid;
  grid-template-columns: 1fr auto auto auto;
  gap: 4px 14px;
  font-size: 12.5px;
  font-variant-numeric: tabular-nums;
}

.impact__table--total-only {
  grid-template-columns: 1fr auto;
}

.impact__col {
  font-family: var(--bc-font-mono);
  font-size: 9.5px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--bc-grey);
  text-align: right;
}

.impact__label {
  color: var(--bc-grey);
  border-top: 1px solid var(--bc-line);
  padding-top: 4px;
}

.impact__value {
  text-align: right;
  border-top: 1px solid var(--bc-line);
  padding-top: 4px;
}

/* the one value the eye should land on */
.impact__value--max {
  color: var(--bc-accent);
}

.impact__label--danger,
.impact__value--danger {
  color: var(--bc-danger);
}
</style>
