<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useLayersStore } from '@/stores/layers'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { recalculateRoutes } from '@/services/trafficAnalysis'
import ImpactStatistics from './ImpactStatistics.vue'
import {
  mdiChevronDown,
  mdiChevronRight,
  mdiRadioboxMarked,
  mdiRadioboxBlank,
  mdiRefresh,
  mdiCalculator,
  mdiDelete,
  mdiClose
} from '@mdi/js'

// Stores
const layersStore = useLayersStore()
const trafficStore = useTrafficAnalysisStore()

// Expansion states
const layersExpanded = ref(true)
const trafficExpanded = ref(false)
const removedEdgesExpanded = ref(true)

// Traffic analysis state
const loadingMessage = ref('')

// Layer selector logic
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

function handleLayerSelection(layerId: string, checked: boolean) {
  if (checked) {
    if (!layersStore.selectedLayers.includes(layerId)) {
      layersStore.updateSelectedLayers([...layersStore.selectedLayers, layerId])
    }
  } else {
    layersStore.updateSelectedLayers(layersStore.selectedLayers.filter((id) => id !== layerId))
  }
}

// Traffic analysis logic
async function calculateRoutes() {
  trafficStore.isCalculating = true
  loadingMessage.value = 'Calculating routes...'
  try {
    const result = await recalculateRoutes(trafficStore.removedEdgesArray)
    trafficStore.setEdgeUsage(
      result.original_edge_usage,
      result.new_edge_usage,
      result.impact_statistics
    )
    console.log(
      `Original: ${result.original_edge_usage.length} edges, New: ${result.new_edge_usage.length} edges`
    )
  } catch (error) {
    console.error('Failed to calculate routes:', error)
  } finally {
    trafficStore.isCalculating = false
  }
}

function removeEdge(u: number, v: number) {
  trafficStore.removeRemovedEdge(u, v)
}

// Watch for traffic panel opening
import { watch } from 'vue'
watch(
  () => trafficStore.isOpen,
  async (isOpen) => {
    if (isOpen) {
      trafficExpanded.value = true
    }
  }
)
</script>

<template>
  <div class="map-controls-panel">
    <!-- Layers Section -->
    <div v-if="layersStore.activeSources.length > 0" class="control-section">
      <div class="section-header" @click="layersExpanded = !layersExpanded">
        <div class="d-flex align-center">
          <v-btn
            :icon="layersExpanded ? mdiChevronDown : mdiChevronRight"
            variant="text"
            density="compact"
            size="small"
          />
          <span class="section-title">LAYERS</span>
        </div>
      </div>
      <v-expand-transition>
        <div v-show="layersExpanded" class="section-content">
          <div v-if="availableLayersFromActiveSources.length === 0" class="text-center py-2">
            <p class="text-caption text-medium-emphasis">No layers available from active sources</p>
          </div>
          <div v-else class="layers-list">
            <div v-for="(layers, sourceId) in layersBySource" :key="sourceId" class="mb-2">
              <h6 class="text-caption font-weight-bold mb-0 text-medium-emphasis">
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
      </v-expand-transition>
    </div>

    <!-- Traffic Analysis Section -->
    <div v-if="trafficStore.isOpen" class="control-section">
      <div class="section-header" @click="trafficExpanded = !trafficExpanded">
        <div class="d-flex align-center flex-grow-1">
          <v-btn
            :icon="trafficExpanded ? mdiChevronDown : mdiChevronRight"
            variant="text"
            density="compact"
            size="small"
          />
          <span class="section-title">TRAFFIC ANALYSIS</span>
        </div>
      </div>
      <v-expand-transition>
        <div v-show="trafficExpanded" class="section-content">
          <!-- Regenerate Pairs -->
          <div class="mb-3">
            <v-btn
              block
              variant="outlined"
              :prepend-icon="mdiRefresh"
              :disabled="trafficStore.isLoading"
              @click="shufflePairs"
            >
              Generate New OD
            </v-btn>
          </div>

          <!-- Removed Edges -->
          <div class="mb-3">
            <div class="d-flex align-center justify-space-between mb-2">
              <div class="d-flex align-center">
                <v-btn
                  :icon="removedEdgesExpanded ? mdiChevronDown : mdiChevronRight"
                  size="x-small"
                  variant="text"
                  @click="removedEdgesExpanded = !removedEdgesExpanded"
                />
                <span class="text-caption font-weight-medium">
                  Removed Edges ({{ trafficStore.removedEdgesCount }})
                </span>
              </div>
              <v-btn
                v-if="trafficStore.removedEdgesCount > 0"
                :icon="mdiDelete"
                size="x-small"
                variant="outlined"
                @click="trafficStore.clearRemovedEdges()"
              />
            </div>
            <v-expand-transition>
              <v-card
                v-show="removedEdgesExpanded"
                variant="outlined"
                flat
                max-height="200px"
                class="overflow-y-auto"
              >
                <v-list v-if="trafficStore.removedEdgesCount > 0" density="compact" class="pa-0">
                  <v-list-item
                    v-for="edge in trafficStore.removedEdgesForDisplay"
                    :key="`${edge.u}-${edge.v}`"
                    class="px-3"
                  >
                    <v-list-item-title class="text-caption">
                      {{ edge.name }}
                      <span v-if="edge.isBidirectional" class="text-grey"> (↔)</span>
                      <span v-else class="text-grey"> ({{ edge.u }}→{{ edge.v }})</span>
                    </v-list-item-title>
                    <template #append>
                      <v-btn
                        :icon="mdiClose"
                        size="x-small"
                        variant="text"
                        @click="removeEdge(edge.u, edge.v)"
                      />
                    </template>
                  </v-list-item>
                </v-list>
                <div v-else class="text-center py-4 text-caption text-medium-emphasis">
                  No edges removed. Click on edges in the visualization to remove them.
                </div>
              </v-card>
            </v-expand-transition>
          </div>

          <!-- Calculate Button -->
          <v-btn
            block
            variant="outlined"
            :prepend-icon="mdiCalculator"
            :disabled="trafficStore.isCalculating"
            @click="calculateRoutes"
          >
            Calculate Routes
          </v-btn>

          <!-- Loading State -->
          <v-progress-linear
            v-if="trafficStore.isLoading || trafficStore.isCalculating"
            indeterminate
            class="my-3"
          />

          <!-- Visualization Layers List -->
          <div v-if="trafficStore.availableVisualizations.length > 0" class="mt-3">
            <div class="text-caption font-weight-medium mb-2">Visualization Layers</div>
            <v-card
              v-for="vis in trafficStore.availableVisualizations"
              :key="vis.value"
              class="visualization-card mb-1 cursor-pointer"
              :class="{ 'active-visualization': trafficStore.activeVisualization === vis.value }"
              variant="outlined"
              density="compact"
              @click="trafficStore.setActiveVisualization(vis.value)"
            >
              <v-card-text class="py-2 px-3">
                <div class="d-flex align-center">
                  <v-icon
                    :icon="
                      trafficStore.activeVisualization === vis.value
                        ? mdiRadioboxMarked
                        : mdiRadioboxBlank
                    "
                    size="small"
                    class="mr-2"
                    :color="trafficStore.activeVisualization === vis.value ? 'primary' : 'grey'"
                  />
                  <div class="text-body-2 font-weight-medium">{{ vis.label }}</div>
                </div>
              </v-card-text>
            </v-card>
          </div>
        </div>
      </v-expand-transition>
    </div>

    <!-- Impact Statistics Section -->
    <ImpactStatistics
      v-if="trafficStore.impactStatistics"
      :statistics="trafficStore.impactStatistics"
    />
  </div>
</template>

<style scoped>
.map-controls-panel {
  position: absolute;
  top: 16px;
  left: 16px;
  z-index: 1000;
  background-color: rgba(var(--v-theme-surface), 0.95);
  backdrop-filter: blur(8px);
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  width: 20vw;
  max-width: 25rem;
  min-width: 300px;
  max-height: calc(100vh - 100px);
  overflow-y: auto;
  transition: all 0.2s ease;
}

.map-controls-panel:hover {
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
}

.control-section {
  border-bottom: 1px solid #e0e0e0;
}

.control-section:last-child {
  border-bottom: none;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  cursor: pointer;
  user-select: none;
}

.section-header:hover {
  background-color: rgba(var(--v-theme-on-surface), 0.05);
}

.section-title {
  font-size: 0.875rem;
  font-weight: 500;
  text-transform: uppercase;
}

.section-content {
  padding: 0 16px 16px 16px;
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

.map-controls-panel::-webkit-scrollbar {
  width: 6px;
}

.map-controls-panel::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.map-controls-panel::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 3px;
}

.map-controls-panel::-webkit-scrollbar-thumb:hover {
  background: #a1a1a1;
}

.cursor-pointer {
  cursor: pointer;
}

.visualization-card {
  transition: all 0.2s ease;
  border-color: #e0e0e0;
}

.visualization-card:hover {
  background-color: rgb(var(--v-theme-surface-variant));
}

.active-visualization {
  background-color: rgb(var(--v-theme-primary-container)) !important;
  border-color: rgb(var(--v-theme-primary)) !important;
}
</style>
