<script setup lang="ts">
import LayerGroups from '@/components/LayerGroups.vue'
import { useLayersStore } from '@/stores/layers'

// Use the layers store
const layersStore = useLayersStore()
</script>

<template>
  <v-card flat class="d-flex flex-column">
    <v-card-title class="flex-shrink-0 text-center pa-6">
      <h4 class="w-100">RESOURCES</h4>
    </v-card-title>
    <v-card-text class="flex-grow-1 d-flex flex-column overflow-hidden">
      <!-- Layer Selection Controls -->
      <div class="mb-6 flex-shrink-0">
        <h5 class="text-subtitle-1 mb-3">Layer Selection</h5>
        <LayerGroups />
      </div>

      <!-- Layer Information -->
      <div class="pt-4 border-t flex-grow-1 d-flex flex-column">
        <h5 class="text-subtitle-1 mb-3 flex-shrink-0">Layer Information</h5>
        <!-- This will show details about selected layers -->
        <div
          v-if="layersStore.selectedLayers.length === 0"
          class="flex-grow-1 d-flex align-center justify-center"
        >
          <p class="text-center text--secondary">Select layers to view information</p>
        </div>
        <div v-else class="overflow-y-auto flex-grow-1 pr-2">
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
</template>
