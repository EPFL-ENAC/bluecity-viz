<script setup lang="ts">
import MapLibreMap from '@/components/MapLibreMap.vue'
import LayerGroups from '@/components/LayerGroups.vue'
import LegendMap from '@/components/LegendMap.vue'
import { useMapLogic } from '@/composables/useMapLogic'

// Use our new composable to handle all the logic
const { map, parameters, center, zoom, theme, themes, syncAllLayersVisibility, layersStore } =
  useMapLogic()
</script>

<template>
  <v-container class="fill-height pa-0 overflow-hidden" fluid>
    <v-row class="fill-height overflow-y-hidden">
      <!-- Collections Column (Left) -->
      <v-col cols="2" class="collections-col border-e-md overflow-y-auto overflow-x-hidden">
        <v-card flat>
          <v-card-title class="ml-2">
            <h4 class="text-center mb-12 mt-6">COLLECTIONS</h4>
          </v-card-title>
          <v-card-text class="d-flex flex-column">
            <!-- Placeholder for configuration selection -->
            <div class="mb-6">
              <h5 class="text-subtitle-1 mb-2">Configuration</h5>
              <v-select
                :items="['Default', 'Custom 1', 'Custom 2']"
                label="Select Configuration"
                outlined
                dense
              ></v-select>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <!-- Visualizations Column (Center) -->
      <v-col cols="8" class="visualizations-col py-0 pl-0 d-flex flex-column position-relative">
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
      </v-col>

      <!-- Resources Column (Right) -->
      <v-col cols="2" class="resources-col border-s-md overflow-y-auto overflow-x-hidden">
        <v-card flat>
          <v-card-title>
            <h4 class="text-center mb-6 mt-4">RESOURCES</h4>
          </v-card-title>
          <v-card-text>
            <!-- Layer Selection Controls -->
            <div class="mb-6">
              <h5 class="text-subtitle-1 mb-3">Layer Selection</h5>
              <LayerGroups />
            </div>

            <!-- Layer Information -->
            <div class="mt-8 pt-4 border-t">
              <h5 class="text-subtitle-1 mb-3">Layer Information</h5>
              <!-- This will show details about selected layers -->
              <div v-if="layersStore.selectedLayers.length === 0">
                <p class="text-center text--secondary">Select layers to view information</p>
              </div>
              <div v-else>
                <div v-for="layerId in layersStore.selectedLayers" :key="layerId" class="mb-4">
                  <h6 class="text-subtitle-2 mb-1">
                    {{ layersStore.possibleLayers.find((l) => l.id === layerId)?.label || layerId }}
                  </h6>
                  <p class="text-caption">
                    {{
                      layersStore.possibleLayers.find((l) => l.id === layerId)?.info ||
                      'No information available'
                    }}
                  </p>
                  <div
                    v-if="layersStore.possibleLayers.find((l) => l.id === layerId)?.attribution"
                    class="text-caption text--secondary"
                  >
                    Source:
                    {{ layersStore.possibleLayers.find((l) => l.id === layerId)?.attribution }}
                  </div>
                </div>
              </div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>
