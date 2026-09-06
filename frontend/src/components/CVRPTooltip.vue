<script setup lang="ts">
import type { CVRPTooltipData } from '@/composables/useDeckGLCVRP'
import { getVehicleColor } from '@/stores/cvrp'
import { computed } from 'vue'

const props = defineProps<{
  data: CVRPTooltipData | null
}>()

const dotColor = computed(() => {
  if (!props.data) return 'transparent'
  const [r, g, b] = getVehicleColor(props.data.routeId)
  return `rgb(${r},${g},${b})`
})

function formatLoad(kg: number): string {
  if (kg >= 1000) return `${(kg / 1000).toFixed(1)} t`
  return `${Math.round(kg)} kg`
}
</script>

<template>
  <div
    v-if="data"
    class="cvrp-tooltip"
    :style="{ left: `${data.x + 15}px`, top: `${data.y + 15}px` }"
  >
    <div class="tooltip-header">
      <span class="vehicle-dot" :style="{ background: dotColor }" />
      Vehicle {{ data.routeId + 1 }}
    </div>

    <div class="tooltip-section">
      <div class="tooltip-row">
        <span class="label">Current load:</span>
        <span class="value">{{ formatLoad(data.loadKg) }}</span>
      </div>
      <div class="tooltip-row">
        <span class="label">Peak load:</span>
        <span class="value">{{ formatLoad(data.maxLoad) }}</span>
      </div>
      <div class="tooltip-row">
        <span class="label">Reload trips:</span>
        <span class="value">{{ data.nTrips }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.cvrp-tooltip {
  position: fixed;
  background: var(--bc-panel);
  color: var(--bc-ink);
  border: 1px solid var(--bc-line);
  padding: 10px 12px;
  min-width: 160px;
  max-width: 260px;
  font-size: 12px;
  pointer-events: none;
  z-index: 1001;
}

.tooltip-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 6px;
}

.vehicle-dot {
  width: 11px;
  height: 11px;
  flex: none;
}

.tooltip-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 1px 0;
}

.label {
  color: var(--bc-grey);
}

.value {
  font-variant-numeric: tabular-nums;
  text-align: right;
}
</style>
