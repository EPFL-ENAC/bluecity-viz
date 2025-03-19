<script setup lang="ts">
import { computed, ref } from 'vue'
import { mdiChevronUp, mdiChevronDown } from '@mdi/js'
import type { MapLayerConfig } from '@/config/layerTypes'
import { type LayerSpecification } from 'maplibre-gl'
import { useLayersStore } from '@/stores/layers'

type LegendColor = {
  color: string
  label: string
  variable?: string
}

const props = defineProps<{
  layers: MapLayerConfig[]
}>()

const store = useLayersStore()

/**
 * Generate legend colors for a given layer's paint property.
 * @param layer The MapLibre layer specification.
 * @returns An array of LegendColor or null if no color stops are found.
 */
const generateLegendColors = (layer: LayerSpecification): LegendColor[] | null => {
  if (layer.paint) {
    // Handle fill-extrusion, line-color, or other paint properties
    const paint = layer.paint as any
    let paintProperty =
      paint['fill-color'] ||
      paint['line-color'] ||
      paint['fill-extrusion-color'] ||
      paint['circle-color'] ||
      null

    if (!paintProperty) return null

    // Handle 'match' expressions for categorical data
    if (Array.isArray(paintProperty) && paintProperty[0] === 'match') {
      const variableProperty = paintProperty[1][1]
      const stops = paintProperty.slice(2)
      const defaultColor = stops.pop()
      const legendColors: LegendColor[] = []

      // Process pairs of value-color in match expression
      for (let i = 0; i < stops.length; i += 2) {
        const value = stops[i]
        const color = stops[i + 1]

        // Only include if we have both a label and a color
        if (value !== undefined && color !== undefined) {
          legendColors.push({
            color: color as string,
            variable: variableProperty,
            label: Array.isArray(value) ? value.join(', ') : String(value)
          })
        }
      }

      // Add default value if it's a color
      if (
        typeof defaultColor === 'string' &&
        defaultColor !== '#000000' &&
        defaultColor !== 'transparent'
      ) {
        legendColors.push({ color: defaultColor, label: 'Other' })
      }

      return legendColors
    }

    // Handle 'interpolate' expressions for continuous data
    if (
      Array.isArray(paintProperty) &&
      paintProperty[0] === 'interpolate' &&
      paintProperty.length > 3
    ) {
      const stops = paintProperty.slice(3) // Skip 'interpolate', 'linear', and the base property
      const legendColors: LegendColor[] = []

      for (let i = 0; i < stops.length; i += 2) {
        legendColors.push({ color: stops[i + 1] as string, label: stops[i].toString() })
      }

      return legendColors
    }
  }

  return null
}

const generateOneLayerWithColors = (layer: MapLayerConfig) => {
  const colors = generateLegendColors(layer.layer) || []
  const paint = layer.layer.paint as any
  const paintProperty =
    paint['fill-color'] ||
    paint['line-color'] ||
    paint['fill-extrusion-color'] ||
    paint['circle-color'] ||
    null

  // Check if the layer is categorical based on paint property expression
  const isCategorical =
    Array.isArray(paintProperty) && (paintProperty[0] === 'match' || paintProperty[0] === 'case')

  return {
    ...layer,
    colors: isCategorical ? colors : colors.reverse(),
    isCategorical,
    variable: paintProperty[1][1],
    gradient: !isCategorical
      ? `linear-gradient(to bottom, ${colors.map((c) => c.color).join(', ')})`
      : undefined
  }
}

const generatedLayersWithColors = computed(() => {
  return props.layers
    .map((layer: MapLayerConfig) => generateOneLayerWithColors(layer))
    .filter((layer) => layer.colors && layer.colors.length > 0)
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

const show = ref(true)
</script>

<template>
  <div v-if="generatedLayersWithColors.length > 0" class="legend">
    <h5 class="legend-title">
      LEGEND
      <v-btn
        :icon="show ? mdiChevronDown : mdiChevronUp"
        flat
        density="compact"
        @click="show = !show"
      ></v-btn>
    </h5>
    <div v-if="show" class="my-2 d-flex d-row ga-10">
      <div
        v-for="layer in generatedLayersWithColors"
        :key="layer?.id"
        class="layer-legend d-flex flex-column justify-space-between"
      >
        <div class="layer-legend-header">
          <h5 class="layer-legend-title">
            {{ layer.label.toUpperCase() }}
          </h5>
          <div v-if="layer.unit" class="layer-legend-unit">{{ layer.unit }}</div>
        </div>
        <!-- Categorical Color Display with Checkboxes -->
        <div v-if="layer?.isCategorical" class="categorical-legend">
          <div v-for="item in layer.colors" :key="item.label" class="legend-item">
            <v-checkbox
              density="compact"
              hide-details
              :model-value="
                !(
                  store.filteredCategories[layer.layer.id] &&
                  store.filteredCategories[layer.layer.id][layer.variable] &&
                  store.filteredCategories[layer.layer.id][layer.variable]?.includes(item.label)
                )
              "
              class="legend-checkbox"
              @update:model-value="(selected:boolean|null) => toggleCategory(layer.layer.id,layer.variable, item.label,selected)"
            >
              <template #label>
                <div class="d-flex align-center">
                  <div class="color-box" :style="{ backgroundColor: item.color }"></div>
                  <div class="label text-body-2">{{ item.label }}</div>
                </div>
              </template>
            </v-checkbox>
          </div>
        </div>
        <!-- Continuous Color Ramp -->
        <div v-else class="gradient-ramp">
          <div class="color-ramp" :style="{ background: layer.gradient }"></div>
          <div class="ramp-labels">
            <span>{{ layer.colors[0].label }}</span>
            <span v-if="layer.colors.length > 2">{{
              layer.colors[~~((layer.colors.length - 1) / 2)].label
            }}</span>
            <span>{{ layer.colors[layer.colors.length - 1].label }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
:deep(.v-checkbox .v-selection-control) {
  min-height: fit-content;
  height: fit-content;
}

.legend {
  position: absolute;
  bottom: 0.5em;
  background-color: rgb(var(--v-theme-surface));
  padding: 0.6em 1.4em;
  z-index: 1000;
  right: 0.5em;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  /* color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity)); */
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  /* max-width: 300px; */
  min-width: 200px;
}

.legend-title {
  margin-bottom: 1em;
  text-align: right;
  padding-bottom: 0.5em;
  width: 100%;
  border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.layer-legend {
  min-height: 200px;
}

.layer-legend-header {
  margin-bottom: 0.5em;
  width: 100%;
  max-width: 200px;
  text-align: left;
}

.layer-legend-title {
  font-weight: 600;
  margin-bottom: 0;
  line-height: 1.2;
}

.layer-legend-unit {
  font-size: 0.75rem;
  color: rgba(var(--v-theme-on-surface), 0.7);
  font-weight: 400;
  margin-top: 2px;
}

/* Update this style since we now handle margin in layer-legend-header */
.layer-legend h5 {
  font-weight: 600;
  width: 100%;
}

.legend-item {
  display: flex;
  align-items: center;
  margin-bottom: 6px;
  width: 100%;
}

.color-box {
  width: 34px;
  height: 24px;
  margin-right: 8px;
  margin-left: 8px;
}

.label {
  margin-right: 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.categorical-legend {
  display: flex;
  flex-direction: column;
  width: 100%;
  max-height: 200px;
  overflow-y: auto;
}

.legend-controls {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.legend-checkbox {
  width: 100%;
}

.gradient-ramp {
  display: flex;
  align-items: center;
  width: 100%;
  height: 100%;
  margin-top: 8px;
}

.color-ramp {
  width: 36px;
  height: 100%;
}

.ramp-labels {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  height: 100%;
  margin-left: 8px;
  font-size: 0.85em;
}
</style>
