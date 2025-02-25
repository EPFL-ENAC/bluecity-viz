<template>
  <div class="legend">
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
        <div v-if="layer?.isCategorical">
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
            <span>{{ layer.colors[~~((layer.colors.length - 1) / 2)].label }}</span>
            <span>{{ layer.colors[layer.colors.length - 1].label }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { mdiChevronUp, mdiChevronDown } from '@mdi/js'
import type { MapLayerConfig } from '@/config/mapConfig'
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
    const paintProperty =
      paint['fill-color'] || paint['line-color'] || paint['fill-extrusion-color'] || null

    if (
      paintProperty &&
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
  console.log(layer)
  if (layer.id === 'wrf') {
    let colors: { color: string; label: string }[] = []
    if (props.variableSelected == 't2') {
      // Color scale for "t2" variable: ["#0d0887","#41049d","#6a00a8","#8f0da4","#b12a90","#cc4778","#e16462","#f2844b","#fca636","#fcce25","#f0f921"]
      // Range: 272 K to 292 K
      colors = [
        { color: '#0d0887', label: '272 K' },
        { color: '#41049d', label: '274 K' },
        { color: '#6a00a8', label: '276 K' },
        { color: '#8f0da4', label: '278 K' },
        { color: '#b12a90', label: '280 K' },
        { color: '#cc4778', label: '282 K' },
        { color: '#e16462', label: '284 K' },
        { color: '#f2844b', label: '286 K' },
        { color: '#fca636', label: '288 K' },
        { color: '#fcce25', label: '290 K' },
        { color: '#f0f921', label: '292 K' }
      ]
    } else if (props.variableSelected == 'u10') {
      // Color scale for "u10" variable: ["#440154","#482475","#414487","#355f8d","#2a788e","#21918c","#22a884","#44bf70","#7ad151","#bddf26","#fde725"]
      // Range: -2 m/s to 3 m/s
      colors = [
        { color: '#440154', label: '-2 m/s' },
        { color: '#482475', label: '-1.5 m/s' },
        { color: '#414487', label: '-1 m/s' },
        { color: '#355f8d', label: '-0.5 m/s' },
        { color: '#2a788e', label: '0 m/s' },
        { color: '#21918c', label: '0.5 m/s' },
        { color: '#22a884', label: '1 m/s' },
        { color: '#44bf70', label: '1.5 m/s' },
        { color: '#7ad151', label: '2 m/s' },
        { color: '#bddf26', label: '2.5 m/s' },
        { color: '#fde725', label: '3 m/s' }
      ]
    } else {
      colors = []
    }
    return {
      ...layer,
      colors,
      isCategorical: false,
      gradient: `linear-gradient(to bottom, ${colors.map((c) => c.color).join(', ')})`
    }
  }

  const colors = generateLegendColors(layer.layer) || []
  const paint = layer.layer.paint as any
  const paintProperty =
    paint['fill-color'] || paint['line-color'] || paint['fill-extrusion-color'] || null

  const isCategorical = paintProperty ? paintProperty[0] !== 'interpolate' : false

  return {
    ...layer,
    colors,
    isCategorical,
    gradient: `linear-gradient(to bottom, ${colors.map((c) => c.color).join(', ')})`
  }
}

const generatedLayersWithColors = computed(() => {
  return props.layers
    .map((layer: MapLayerConfig) => generateOneLayerWithColors(layer))
    .filter((layer) => layer.colors && layer.colors.length > 0)
})

const show = ref(true)
</script>
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
}

.layer-legend {
  margin-bottom: 1em;
  margin-left: 2em;
}

.layer-legend h5 {
  margin-bottom: 0.5em;
  max-width: 100px;
}

.legend-item {
  display: flex;
  align-items: center;
  margin-bottom: 4px;
  width: 100%;
}

.color-box {
  width: 40px;
  height: 25px;
  margin-right: 8px;
}

.label,
.code {
  margin-right: 8px;
}

.gradient-ramp {
  display: flex; /* Set display to flex */
  align-items: center; /* Align items vertically */
  width: 100%; /* Full width to accommodate labels next to the ramp */
  height: 150px; /* Adjust height for better gradient visualization */
}

.color-ramp {
  width: 40px; /* Fixed width for the color ramp */
  height: 100%;
}

.ramp-labels {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  height: 100%;
  margin-left: 10px; /* Add some spacing between ramp and labels */
}
</style>
