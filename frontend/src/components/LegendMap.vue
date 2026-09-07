<script setup lang="ts">
import type { MapLayerConfig } from '@/config/layerTypes'
import { getVehicleColor, useCVRPStore } from '@/stores/cvrp'
import { useLayersStore } from '@/stores/layers'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import {
  trafficLegend as buildTrafficLegend,
  datasetLegend,
  type LegendColor,
  type TrafficLegendMode
} from '@/utils/legendColor'
import { interpolateViridis } from 'd3-scale-chromatic'
import { computed } from 'vue'

const props = defineProps<{
  layers: MapLayerConfig[]
}>()

const store = useLayersStore()
const trafficStore = useTrafficAnalysisStore()
const cvrpStore = useCVRPStore()

const generatedLayersWithColors = computed(() => {
  return props.layers
    .map((layer: MapLayerConfig) => datasetLegend(layer))
    .filter((layer) => layer.colors && layer.colors.length > 0)
})

// Generate traffic analysis legend
const trafficLegend = computed(() => {
  // Read these so the computed tracks them
  const mode = trafficStore.activeVisualization
  const scale = trafficStore.colorScale
  const min = trafficStore.minValue
  const max = trafficStore.maxValue

  if (!trafficStore.isOpen || mode === 'none' || !scale) {
    return null
  }

  return buildTrafficLegend(mode as TrafficLegendMode, min, max, trafficStore.getColor)
})
// Generate CVRP legend
const cvrpLegend = computed(() => {
  if (!cvrpStore.isOpen || !cvrpStore.hasResult || !cvrpStore.lastResult) return null

  if (cvrpStore.visualizationMode === 'heatmap') {
    const steps = 40
    const max = cvrpStore.edgeLoadMax
    const colors: LegendColor[] = []
    for (let i = 0; i < steps; i++) {
      const t = i / (steps - 1)
      const value = max * (1 - t)
      const hex = interpolateViridis(1 - t)
      colors.push({
        color: hex,
        label: value >= 1000 ? `${(value / 1000).toFixed(1)}k` : Math.round(value).toString()
      })
    }
    return {
      label: 'Edge Load',
      unit: `Total load (${cvrpStore.lastResult.load_unit})`,
      colors,
      gradient: `linear-gradient(to left, ${colors.map((c) => c.color).join(', ')})`,
      isCategorical: false,
      showZero: false
    }
  }

  // Routes mode: one color swatch per vehicle (simple swatches, no MapLibre filter checkboxes)
  const nRoutes = cvrpStore.lastResult.n_routes
  const colors: LegendColor[] = Array.from({ length: nRoutes }, (_, i) => {
    const [r, g, b] = getVehicleColor(i)
    return { color: `rgb(${r},${g},${b})`, label: `Vehicle ${i + 1}` }
  })
  return {
    label: 'Vehicle Routes',
    unit: `${nRoutes} vehicle${nRoutes !== 1 ? 's' : ''}`,
    colors,
    isSwatches: true,
    isCategorical: false,
    gradient: undefined
  }
})

// Combine MapLibre and traffic legends
const allLegends = computed<Record<string, any>[]>(() => {
  const legends: Record<string, any>[] = [...generatedLayersWithColors.value]
  if (trafficLegend.value) {
    legends.push(trafficLegend.value as any)
  }
  if (cvrpLegend.value) {
    legends.push(cvrpLegend.value as any)
  }
  return legends
})

// Toggle category selection
const toggleCategory = (
  layerId: string,
  variable: string,
  category: string,
  selected: boolean | null
) => {
  if (!store.filteredCategories[layerId]) {
    store.filteredCategories[layerId] = {}
  }
  if (!store.filteredCategories[layerId][variable]) {
    store.filteredCategories[layerId][variable] = []
  }
  const layerFilteredCategories = store.filteredCategories[layerId][variable] ?? []

  if (selected) {
    store.filterOutCategories(
      layerId,
      variable,
      layerFilteredCategories.filter((c) => c !== category)
    )
  } else if (!selected) {
    store.filterOutCategories(layerId, variable, [...layerFilteredCategories, category])
  }
}

const shouldShowLegend = computed(() => {
  return allLegends.value.length > 0 || trafficLegend.value !== null
})
</script>

<template>
  <div v-if="shouldShowLegend" class="legend">
    <div v-for="layer in allLegends" :key="layer?.id || layer?.label" class="block">
      <div class="bc-micro block__title">
        {{ layer.label }}<span v-if="layer.unit"> · {{ layer.unit }}</span>
      </div>

      <!-- Categorical: the square is the filter toggle -->
      <div v-if="layer?.isCategorical" class="cats">
        <div
          v-for="item in layer.colors"
          :key="item.label"
          class="cat"
          @click="
            toggleCategory(
              layer.layer.id,
              layer.variable,
              item.label,
              !!(
                store.filteredCategories[layer.layer.id] &&
                store.filteredCategories[layer.layer.id][layer.variable] &&
                store.filteredCategories[layer.layer.id][layer.variable]?.includes(item.label)
              )
            )
          "
        >
          <span
            class="cat__box"
            :style="{
              backgroundColor:
                store.filteredCategories[layer.layer.id] &&
                store.filteredCategories[layer.layer.id][layer.variable] &&
                store.filteredCategories[layer.layer.id][layer.variable]?.includes(item.label)
                  ? 'transparent'
                  : item.color,
              borderColor: item.color
            }"
          />
          <span class="cat__label">{{ item.label }}</span>
        </div>
      </div>

      <!-- Vehicle routes: line chips, two columns -->
      <div v-else-if="layer?.isSwatches" class="vehicles">
        <span v-for="item in layer.colors" :key="item.label" class="vehicle">
          <span class="vehicle__line" :style="{ backgroundColor: item.color }" />
          {{ item.label }}
        </span>
      </div>

      <!-- Continuous ramp -->
      <div v-else>
        <div class="ramp" :style="{ background: layer.gradient }"></div>
        <div class="ramp__labels">
          <span>{{ layer.colors[layer.colors.length - 1].label }}</span>
          <span v-if="layer.showZero">0</span>
          <span v-else-if="layer.colors.length > 2">{{
            layer.colors[~~((layer.colors.length - 1) / 2)].label
          }}</span>
          <span>{{ layer.colors[0].label }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.legend {
  position: absolute;
  left: 24px;
  bottom: 22px;
  background: var(--bc-legend-bg);
  padding: 10px 12px;
  z-index: 1;
  max-height: calc(100% - 60px);
  overflow-y: auto;
}

.block + .block {
  margin-top: 10px;
}

.block__title {
  margin-bottom: 6px;
}

.ramp {
  width: 220px;
  height: 6px;
}

.ramp__labels {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
  font-family: var(--bc-font-mono);
  font-size: var(--bc-fs-micro);
  color: var(--bc-ink);
}

.cats {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-width: 220px;
}

.cat {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.cat__box {
  width: 11px;
  height: 11px;
  flex: none;
  border: 1px solid;
}

.cat__label {
  font-family: var(--bc-font-mono);
  font-size: var(--bc-fs-micro);
  color: var(--bc-ink);
}

.vehicles {
  display: grid;
  grid-template-columns: auto auto;
  gap: 4px 20px;
  font-family: var(--bc-font-mono);
  font-size: var(--bc-fs-micro);
  color: var(--bc-ink);
}

.vehicle {
  display: flex;
  align-items: center;
  gap: 8px;
}

.vehicle__line {
  width: 16px;
  height: 2px;
  flex: none;
}
</style>
