<script setup lang="ts">
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

function formatWithSign(value: number, decimals = 1): string {
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(decimals)}`
}

function formatCo2(grams?: number): string {
  if (grams == null) return '—'
  // grams get big fast on the total column
  if (Math.abs(grams) >= 1000) return `${formatWithSign(grams / 1000, 1)} kg`
  return `${formatWithSign(grams, 0)} g`
}

const affectedPercent = computed(() => {
  const s = props.statistics
  if (!s || s.total_routes === 0) return '0.0'
  return ((s.affected_routes / s.total_routes) * 100).toFixed(1)
})

const header = computed(() => {
  const s = props.statistics
  if (!s) return 'Impact'
  if (props.elasticDemand) return 'Impact · system-level total'
  return `Impact · ${s.total_routes} routes, ${s.affected_routes} affected (${affectedPercent.value}%)`
})

// One row per measure, with the three columns of the design.
const rows = computed(() => {
  const s = props.statistics
  if (!s) return []
  return [
    {
      key: 'Distance',
      total: `${formatWithSign(s.total_distance_increase_km, 1)} km`,
      avg: `${formatWithSign(s.avg_distance_increase_km, 2)} km`,
      max: `${formatWithSign(s.max_distance_increase_km, 2)} km`
    },
    {
      key: 'Time',
      total: `${formatWithSign(s.total_time_increase_minutes, 0)} min`,
      avg: `${formatWithSign(s.avg_time_increase_minutes, 1)} min`,
      max: `${formatWithSign(s.max_time_increase_minutes, 1)} min`
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
