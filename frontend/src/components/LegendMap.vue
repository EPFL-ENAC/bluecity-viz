<script setup lang="ts">
import { computed, ref } from 'vue'
import { mdiChevronUp, mdiChevronDown } from '@mdi/js'
import type { MapLayerConfig } from '@/config/layerTypes'
import type { LayerSpecification } from 'maplibre-gl'

type LegendColor = {
  color: string
  label: string
}

const props = defineProps<{
  layers: MapLayerConfig[]
  variableSelected: string
}>()

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
      paint['fill-color'] || paint['line-color'] || paint['fill-extrusion-color'] || null

    if (!paintProperty) return null

    // Handle 'match' expressions for categorical data
    if (Array.isArray(paintProperty) && paintProperty[0] === 'match') {
      const property = paintProperty[1]
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
    paint['fill-color'] || paint['line-color'] || paint['fill-extrusion-color'] || null

  // Check if the layer is categorical based on paint property expression
  const isCategorical =
    Array.isArray(paintProperty) && (paintProperty[0] === 'match' || paintProperty[0] === 'case')

  return {
    ...layer,
    colors: isCategorical ? colors : colors.reverse(),
    isCategorical,
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

const show = ref(true)
</script>

<template>
  <div v-if="generatedLayersWithColors.length > 0" class="legend">
    <h4>
      Legend
      <v-btn
        :icon="show ? mdiChevronDown : mdiChevronUp"
        flat
        density="compact"
        @click="show = !show"
      ></v-btn>
    </h4>
    <div v-if="show" class="my-2 d-flex d-row">
      <div
        v-for="layer in generatedLayersWithColors"
        :key="layer?.id"
        class="layer-legend d-flex flex-column justify-space-between"
      >
        <h5>{{ layer.label }} {{ layer.unit ? '(' + layer.unit + ')' : '' }}</h5>
        <!-- Categorical Color Display -->
        <div v-if="layer?.isCategorical" class="categorical-legend">
          <div v-for="item in layer.colors" :key="item.label" class="legend-item">
            <div class="color-box" :style="{ backgroundColor: item.color }"></div>
            <div class="label text-body-2">{{ item.label }}</div>
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
.legend {
  position: absolute;
  bottom: 0.5em;
  background-color: rgb(var(--v-theme-surface));
  padding: 0.6em 1.4em;
  border-radius: 0.3em;
  z-index: 1000;
  right: 0.5em;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  max-width: 300px;
  min-width: 200px;
}

.layer-legend {
  margin-bottom: 1em;
  width: 100%;
}

.layer-legend h5 {
  margin-bottom: 0.5em;
  font-weight: 600;
  text-align: left;
  width: 100%;
}

.legend-item {
  display: flex;
  align-items: center;
  margin-bottom: 6px;
  width: 100%;
}

.color-box {
  width: 24px;
  height: 24px;
  margin-right: 8px;
  border-radius: 4px;
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

.gradient-ramp {
  display: flex;
  align-items: center;
  width: 100%;
  height: 150px;
  margin-top: 8px;
}

.color-ramp {
  width: 36px;
  height: 100%;
  border-radius: 4px;
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
