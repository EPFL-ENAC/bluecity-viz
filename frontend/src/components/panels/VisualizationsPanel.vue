<script setup lang="ts">
import MapLibreMap from '@/components/MapLibreMap.vue'
import LegendMap from '@/components/LegendMap.vue'
import LayerSelector from '@/components/LayerSelector.vue'
import { useMapLogic } from '@/composables/useMapLogic'

// Use the map logic composable
const { map, parameters, center, zoom, theme, themes, syncAllLayersVisibility, layersStore } =
  useMapLogic()
</script>

<template>
  <div class="visualizations-panel position-relative fill-height">
    <MapLibreMap
      :key="theme"
      ref="map"
      :center="center"
      :style-spec="theme"
      :popup-layer-ids="parameters.popupLayerIds"
      :zoom="zoom"
      :max-zoom="20"
      :min-zoom="6"
      :callback-loaded="() => syncAllLayersVisibility(layersStore.selectedLayers)"
      class="fill-height"
    >
      <template #legend>
        <legend-map :layers="layersStore.visibleLayers"></legend-map>
      </template>
    </MapLibreMap>

    <!-- Layer Selector -->
    <LayerSelector />

    <div class="theme-selector position-absolute top-0 right-0 ma-4">
      <v-select
        v-model="theme"
        :items="themes"
        item-value="value"
        item-title="label"
        label="Theme"
        dense
        hide-details
        outlined
        style="width: 150px"
      />
    </div>
  </div>
</template>

<style scoped>
.visualizations-panel {
  position: relative;
}

.theme-selector {
  z-index: 1000;
}
</style>
