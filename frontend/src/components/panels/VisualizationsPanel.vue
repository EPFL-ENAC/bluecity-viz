<script setup lang="ts">
import MapLibreMap from '@/components/MapLibreMap.vue'
import LegendMap from '@/components/LegendMap.vue'
import LayerSelector from '@/components/LayerSelector.vue'
import { useMapLogic } from '@/composables/useMapLogic'

// Use the map logic composable
const { map, parameters, center, zoom, syncAllLayersVisibility, layersStore } = useMapLogic()
</script>

<template>
  <div class="visualizations-panel position-relative fill-height">
    <MapLibreMap
      ref="map"
      :center="center"
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
  </div>
</template>

<style scoped>
.visualizations-panel {
  position: relative;
}
</style>
