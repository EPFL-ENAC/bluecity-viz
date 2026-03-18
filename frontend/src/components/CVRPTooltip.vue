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
  z-index: 1001;
  background: rgba(255, 255, 255, 0.98);
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 12px;
  min-width: 170px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  font-size: 13px;
  pointer-events: none;
}

.tooltip-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 14px;
  color: #1a1a1a;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid #eee;
}

.vehicle-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex-shrink: 0;
}

.tooltip-section {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.tooltip-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 2px 0;
}

.label {
  color: #666;
  font-size: 12px;
}

.value {
  font-weight: 500;
  color: #1a1a1a;
}
</style>
