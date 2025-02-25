<script setup lang="ts">
import MapLibreMap from '@/components/MapLibreMap.vue'
import { useTheme } from 'vuetify'

import type { Parameters } from '@/utils/jsonWebMap'
import { computed, ref, shallowRef, watch } from 'vue'
import CustomSlider from '@/components/CustomSlider.vue'
import InfoTooltip from '@/components/InfoTooltip.vue'
import LegendMap from '@/components/LegendMap.vue'
import { mapConfig } from '@/config/mapConfig'
// const props = defineProps<{
//   styleUrl: string
// }>()

const map = ref<InstanceType<typeof MapLibreMap>>()

const parameters = shallowRef<Parameters>({})

const variableSelected = ref<string>('u10')

const idxImage = ref<number>(0)

const center = {
  lat: 46.882,
  lng: 8.1321
}

const zoom = 8

const possibleLayers = mapConfig.layers.map((d) => ({
  id: d.layer.id,
  label: d.label,
  info: d.info
}))

const layersSelected = ref<string[]>(['roads_swiss_statistics-layer'])

const layersVisible = computed(() => {
  return mapConfig.layers.filter((layer) => layersSelected.value.includes(layer.layer.id) ?? false)
})

const isWrfSelected = computed(() => layersSelected.value.includes('wrf-layer'))

const syncAllLayersVisibility = (layersSelected: string[]) => {
  for (let { id: layer } of possibleLayers) {
    if (layersSelected.includes(layer)) {
      map.value?.setLayerVisibility(layer, true)
    } else {
      map.value?.setLayerVisibility(layer, false)
    }
  }
}
watch(
  () => layersSelected.value,
  (layersSelected) => {
    syncAllLayersVisibility(layersSelected)
  }
)

const vuetifyTheme = useTheme()

const theme = ref('style/dark.json') // Default theme
const themes = [
  { value: 'style/light.json', label: 'Light' },
  { value: 'style/dark.json', label: 'Dark' },
  { value: 'style/none.json', label: 'None' }
]

watch(
  () => theme.value,
  (theme) => {
    vuetifyTheme.global.name.value = theme === 'style/light.json' ? 'light' : 'dark'
  }
)
</script>

<template>
  <v-container class="fill-height pa-0 overflow-hidden" fluid>
    <v-row class="fill-height overflow-y-hidden">
      <v-col cols="2" class="params-col border-e-md overflow-y-auto overflow-x-hidden">
        <v-card flat>
          <v-card-title class="ml-2"> <h2>LAYERS</h2> </v-card-title>
          <v-card-text class="d-flex flex-column">
            <v-checkbox
              v-for="(item, index) in possibleLayers"
              :key="index"
              v-model="layersSelected"
              class="py-2"
              :hide-details="!(isWrfSelected && item.id == 'wrf-layer')"
              :value="item.id"
            >
              <template #label>
                <h4>{{ item.label.toUpperCase() }}</h4>
              </template>
              <template #append>
                <info-tooltip>{{ item.info }}</info-tooltip>
              </template>
              <template v-if="isWrfSelected && item.id == 'wrf-layer'" #details>
                <v-radio-group
                  v-if="item.id == 'wrf-layer' && isWrfSelected"
                  v-model="variableSelected"
                  hide-details
                >
                  <v-radio label="Windspeed" value="u10"></v-radio>
                  <v-radio label="Temperature" value="t2"></v-radio>
                </v-radio-group>
              </template>
            </v-checkbox>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col id="map-time-input-container" cols="10" class="py-0 pl-0 d-flex flex-column">
        <MapLibreMap
          :key="theme"
          ref="map"
          :center="center"
          :style-spec="theme"
          :popup-layer-ids="parameters.popupLayerIds"
          :zoom="zoom"
          :max-zoom="20"
          :min-zoom="6"
          :idx-image="idxImage"
          :variable-selected="variableSelected"
          :callback-loaded="() => syncAllLayersVisibility(layersSelected)"
          class="flex-grow-1"
        >
          <template #legend>
            <legend-map
              :layers="layersVisible"
              :variable-selected="variableSelected"
              :is-continuous="true"
            ></legend-map>
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
        <v-card v-if="isWrfSelected" flat class="mt-auto border-t-md pb-4 px-4">
          <v-card-title> Time </v-card-title>
          <v-card-text>
            <custom-slider v-model="idxImage"> </custom-slider>
          </v-card-text>
        </v-card>
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
