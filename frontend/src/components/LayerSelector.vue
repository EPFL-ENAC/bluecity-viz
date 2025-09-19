<script setup lang="ts">
import { useLayersStore } from '@/stores/layers'
import { computed, ref } from 'vue'
import { mdiChevronUp, mdiChevronDown } from '@mdi/js'

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

const show = ref(true)
</script>

<template>
  <div v-if="layersStore.activeSources.length > 0" class="layer-selector">
    <div class="layer-title" :class="{ 'with-divider': show }">
      <span>LAYERS</span>
      <v-btn
        :icon="show ? mdiChevronDown : mdiChevronUp"
        variant="text"
        density="compact"
        size="small"
        @click="show = !show"
      />
    </div>
    <div v-if="show" class="layer-content">
      <div v-if="availableLayersFromActiveSources.length === 0" class="text-center py-2">
        <p class="text-caption text--secondary">No layers available from active sources</p>
      </div>
      <div v-else class="layers-list">
        <!-- Group by source -->
        <div v-for="(layers, sourceId) in layersBySource" :key="sourceId" class="mb-2">
          <h6 class="text-caption font-weight-bold mb-0 text--primary">
            {{ layers[0]?.sourceLabel }}
          </h6>
          <div class="ml-1">
            <div v-for="layer in layers" :key="layer.id" class="d-flex align-center py-0">
              <v-checkbox
                :model-value="layersStore.selectedLayers.includes(layer.id)"
                class="ma-0 mr-2"
                color="primary"
                hide-details
                density="compact"
                @update:model-value="(checked) => handleLayerSelection(layer.id, !!checked)"
              />
              <div
                class="flex-grow-1"
                @click="
                  handleLayerSelection(layer.id, !layersStore.selectedLayers.includes(layer.id))
                "
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
    </div>
  </div>
</template>

<style scoped>
.layer-selector {
  position: absolute;
  top: 16px;
  left: 16px;
  z-index: 1000;
  background-color: rgba(var(--v-theme-surface), 0.8);
  padding: 16px;
  display: flex;
  flex-direction: column;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  width: 20vw;
  max-width: 25rem;
  transition: all 0.2s ease;
}

.layer-selector:hover {
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
}

.layer-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  font-size: 0.875rem;
  font-weight: 400;
  text-transform: uppercase;
}

.layer-title.with-divider {
  padding-bottom: 12px;
  border-bottom: 1px solid #e0e0e0;
}

.layer-content {
  padding-top: 12px;
  margin-bottom: 12px;
}

.layers-list {
  max-height: 400px;
  overflow-y: auto;
  padding-right: 4px;
}

.layers-list::-webkit-scrollbar {
  width: 4px;
}

.layers-list::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 2px;
}

.layers-list::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 2px;
}

.layers-list::-webkit-scrollbar-thumb:hover {
  background: #a1a1a1;
}

.cursor-pointer {
  cursor: pointer;
}
</style>
