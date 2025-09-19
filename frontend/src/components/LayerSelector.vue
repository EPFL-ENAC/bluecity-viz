<script setup lang="ts">
import { useLayersStore } from '@/stores/layers'
import { computed } from 'vue'

// Use the layers store
const layersStore = useLayersStore()

// Get layers from active sources
const availableLayersFromActiveSources = computed(() => {
  const layers: Array<{
    id: string
    label: string
    info?: string
    sourceLabel: string
    sourceId: string
  }> = []

  layersStore.activeSources.forEach((sourceId) => {
    const layersFromSource = layersStore.getLayersBySource(sourceId)
    const source = layersStore.availableSources.find((s) => s.id === sourceId)

    layersFromSource.forEach((layer) => {
      layers.push({
        id: layer.layer.id,
        label: layer.label,
        info: layer.info,
        sourceLabel: source?.label || sourceId,
        sourceId: sourceId
      })
    })
  })

  return layers
})

// Handle layer selection change
function handleLayerSelection(layerId: string, checked: boolean) {
  if (checked) {
    // Add layer to selection
    if (!layersStore.selectedLayers.includes(layerId)) {
      layersStore.updateSelectedLayers([...layersStore.selectedLayers, layerId])
    }
  } else {
    // Remove layer from selection
    layersStore.updateSelectedLayers(layersStore.selectedLayers.filter((id) => id !== layerId))
  }
}

// Check if layer is selected
function isLayerSelected(layerId: string): boolean {
  return layersStore.selectedLayers.includes(layerId)
}

// Group layers by source for better organization
const layersBySource = computed(() => {
  const grouped: Record<
    string,
    Array<{
      id: string
      label: string
      info?: string
      sourceLabel: string
      sourceId: string
    }>
  > = {}

  availableLayersFromActiveSources.value.forEach((layer) => {
    if (!grouped[layer.sourceId]) {
      grouped[layer.sourceId] = []
    }
    grouped[layer.sourceId].push(layer)
  })

  return grouped
})
</script>

<template>
  <v-card v-if="layersStore.activeSources.length > 0" class="layer-selector" variant="flat">
    <v-card-text class="pa-4">
      <div v-if="availableLayersFromActiveSources.length === 0" class="text-center py-2">
        <p class="text-caption text--secondary">No layers available from active sources</p>
      </div>
      <div v-else>
        <!-- Group by source -->
        <div v-for="(layers, sourceId) in layersBySource" :key="sourceId" class="mb-2">
          <h6 class="text-caption font-weight-bold mb-0 text--primary">
            {{ layers[0]?.sourceLabel }}
          </h6>
          <div class="ml-1">
            <div v-for="layer in layers" :key="layer.id" class="d-flex align-center py-0">
              <v-checkbox
                :model-value="isLayerSelected(layer.id)"
                class="mr-1"
                color="primary"
                hide-details
                density="compact"
                @update:model-value="(checked) => handleLayerSelection(layer.id, !!checked)"
              />
              <div
                class="flex-grow-1"
                @click="handleLayerSelection(layer.id, !isLayerSelected(layer.id))"
              >
                <v-tooltip :text="layer.info || 'No additional information'" location="right">
                  <template #activator="{ props }">
                    <div v-bind="props" class="text-body-2 cursor-pointer">
                      {{ layer.label }}
                    </div>
                  </template>
                </v-tooltip>
              </div>
            </div>
          </div>
        </div>
      </div>
    </v-card-text>
  </v-card>
</template>

<style scoped>
.layer-selector {
  position: absolute;
  top: 16px;
  left: 16px;
  z-index: 1000;
  max-width: 300px;
  max-height: 80vh;
  overflow-y: auto;
  background-color: rgba(255, 255, 255, 0);
}

.layer-selector .v-card-text {
  overflow-y: auto;
}

.cursor-pointer {
  cursor: pointer;
}
</style>
