<script setup lang="ts">
import MapLibreMap from '@/components/MapLibreMap.vue'
import { useTheme } from 'vuetify'

import type { Parameters } from '@/utils/jsonWebMap'
import { ref, shallowRef, watch } from 'vue'
import LegendMap from '@/components/LegendMap.vue'
import LayerGroups from '@/components/LayerGroups.vue'
import { useLayersStore } from '@/stores/layers'

const map = ref<InstanceType<typeof MapLibreMap>>()

const parameters = shallowRef<Parameters>({})

const center = {
  lat: 46.52,
  lng: 6.63
}

const zoom = 11

const layersStore = useLayersStore()

// Sync layer visibility with the map when the selected layers change
const syncAllLayersVisibility = (layersSelected: string[]) => {
  for (let { id: layerID } of layersStore.possibleLayers) {
    if (layersSelected.includes(layerID)) {
      map.value?.setLayerVisibility(layerID, true)
    } else {
      map.value?.setLayerVisibility(layerID, false)
    }
  }
}

watch(() => layersStore.selectedLayers, syncAllLayersVisibility, { immediate: true, deep: true })

const vuetifyTheme = useTheme()

const theme = ref('style/light.json') // Default theme
const themes = [
  { value: 'style/light.json', label: 'Light' },
  { value: 'style/dark.json', label: 'Dark' },
  { value: 'style/none.json', label: 'None' }
]

watch(
  () => theme.value,
  (newTheme) => {
    vuetifyTheme.global.name.value = newTheme === 'style/light.json' ? 'light' : 'dark'
  },
  { immediate: true }
)
</script>

<template>
  <v-container class="fill-height pa-0 overflow-hidden" fluid>
    <v-row class="fill-height overflow-y-hidden">
      <v-col xl="2" cols="3" class="params-col border-e-md overflow-y-auto overflow-x-hidden">
        <v-card flat>
          <v-card-title class="ml-2"> <h4 class="text-center mb-12 mt-6">LAYERS</h4> </v-card-title>
          <v-card-text class="d-flex flex-column">
            <!-- Use the new LayerGroups component -->
            <LayerGroups />
          </v-card-text>
        </v-card>
      </v-col>
      <v-col id="map-time-input-container" xl="10" cols="9" class="py-0 pl-0 d-flex flex-column">
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
          class="flex-grow-1"
        >
          <template #legend>
            <legend-map :layers="layersStore.visibleLayers"></legend-map>
          </template>
        </MapLibreMap>
        <div class="theme-selector">
          <v-select
            v-model="theme"
            :items="themes"
            item-value="value"
            item-title="label"
            label="Theme"
            dense
            hide-details
            outlined
          />
        </div>
      </v-col>
    </v-row>
  </v-container>
</template>

<style scoped>
.v-slider-thumb__label span.thumb-label-nowrap {
  white-space: nowrap;
}

.params-col {
  max-height: 100vh;
}

.no-min-height {
  height: 32px;
}

.theme-selector {
  position: absolute;
  top: 12px;
  right: 56px;
  z-index: 1000;
}
</style>
