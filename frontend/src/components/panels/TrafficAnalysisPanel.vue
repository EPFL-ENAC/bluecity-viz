<script setup lang="ts">
import { ref, onMounted, watch, inject, type Ref } from 'vue'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { fetchGraphData, generateRandomPairs, recalculateRoutes } from '@/services/trafficAnalysis'
import {
  mdiClose,
  mdiRefresh,
  mdiCalculator,
  mdiDelete,
  mdiChevronDown,
  mdiChevronRight
} from '@mdi/js'

const trafficStore = useTrafficAnalysisStore()
const removedEdgesExpanded = ref(true)
const loadingMessage = ref('')

// Inject the map reference from parent
const mapRef = inject<Ref<any>>('mapRef')

onMounted(async () => {
  await loadGraphData()
  await shufflePairs()
})

// Watch for graph edges being loaded and add them to the map
watch(
  () => trafficStore.graphEdges,
  (edges) => {
    if (edges.length > 0 && mapRef?.value?.trafficAnalysisMap) {
      mapRef.value.trafficAnalysisMap.addGraphEdgesLayer(edges)
    }
  }
)

// Watch for panel opening/closing
watch(
  () => trafficStore.isOpen,
  (isOpen) => {
    if (!mapRef?.value?.trafficAnalysisMap) return

    if (isOpen) {
      // Add graph edges when panel opens
      if (trafficStore.graphEdges.length > 0) {
        mapRef.value.trafficAnalysisMap.addGraphEdgesLayer(trafficStore.graphEdges)
      }
      // Attach click listener
      mapRef.value.trafficAnalysisMap.attachEdgeClickListener(handleEdgeClick)
    } else {
      // Remove graph edges and routes when panel closes
      mapRef.value.trafficAnalysisMap.removeGraphEdgesLayer()
      mapRef.value.trafficAnalysisMap.clearRoutes()
      mapRef.value.trafficAnalysisMap.detachEdgeClickListener()
    }
  }
)

// Watch for removed edges changes
watch(
  () => trafficStore.removedEdgesArray,
  (removedEdges) => {
    if (mapRef?.value?.trafficAnalysisMap) {
      mapRef.value.trafficAnalysisMap.updateRemovedEdges(removedEdges)
    }
  },
  { deep: true }
)

// Watch for route comparisons
watch(
  () => trafficStore.comparisons,
  (comparisons) => {
    if (comparisons.length > 0 && mapRef?.value?.trafficAnalysisMap) {
      mapRef.value.trafficAnalysisMap.visualizeRoutes(comparisons)
    }
  }
)

function handleEdgeClick(u: number, v: number) {
  if (trafficStore.clickMode === 'remove') {
    trafficStore.addRemovedEdge(u, v)
  } else {
    trafficStore.removeRemovedEdge(u, v)
  }
}

async function loadGraphData() {
  trafficStore.isLoading = true
  loadingMessage.value = 'Loading graph data...'
  try {
    const graphData = await fetchGraphData()
    trafficStore.setGraphEdges(graphData.edges)
    console.log(`Loaded ${graphData.edge_count} edges from graph`)
  } catch (error) {
    console.error('Failed to load graph data:', error)
  } finally {
    trafficStore.isLoading = false
  }
}

async function shufflePairs() {
  trafficStore.isLoading = true
  loadingMessage.value = 'Generating random pairs...'
  try {
    const pairs = await generateRandomPairs(5)
    trafficStore.setNodePairs(pairs)
    trafficStore.clearResults()
    // Clear routes visualization when shuffling
    if (mapRef?.value?.trafficAnalysisMap) {
      mapRef.value.trafficAnalysisMap.clearRoutes()
    }
  } catch (error) {
    console.error('Failed to generate pairs:', error)
  } finally {
    trafficStore.isLoading = false
  }
}

async function calculateRoutes() {
  trafficStore.isCalculating = true
  loadingMessage.value = 'Calculating routes...'
  try {
    const result = await recalculateRoutes(trafficStore.nodePairs, trafficStore.removedEdgesArray)
    trafficStore.setComparisons(result.comparisons)
    console.log(`Calculated ${result.comparisons.length} route comparisons`)
  } catch (error) {
    console.error('Failed to calculate routes:', error)
  } finally {
    trafficStore.isCalculating = false
  }
}

function removeEdge(u: number, v: number) {
  trafficStore.removeRemovedEdge(u, v)
}

function closePanel() {
  trafficStore.closePanel()
}
</script>

<template>
  <v-card v-if="trafficStore.isOpen" class="traffic-analysis-panel" variant="outlined" flat>
    <v-card-title class="d-flex align-center justify-space-between pa-3 border-b-sm">
      <span class="text-subtitle-1">TRAFFIC ANALYSIS</span>
      <v-btn :icon="mdiClose" variant="text" size="small" @click="closePanel" />
    </v-card-title>

    <v-card-text class="pa-3">
      <!-- Loading State -->
      <v-progress-linear
        v-if="trafficStore.isLoading || trafficStore.isCalculating"
        indeterminate
        class="mb-3"
      />
      <div v-if="trafficStore.isLoading || trafficStore.isCalculating" class="text-center mb-3">
        <p class="text-caption text-medium-emphasis">{{ loadingMessage }}</p>
      </div>

      <!-- Click Mode Toggle -->
      <div class="mb-3">
        <div class="d-flex align-center justify-space-between">
          <span class="text-caption">Click Mode:</span>
          <v-switch
            :model-value="trafficStore.clickMode === 'add'"
            density="compact"
            hide-details
            inset
            @update:model-value="trafficStore.toggleClickMode()"
          >
            <template #label>
              <span class="text-caption">
                {{ trafficStore.clickMode === 'remove' ? 'Remove' : 'Add' }}
              </span>
            </template>
          </v-switch>
        </div>
      </div>

      <!-- Origin-Destination Pairs -->
      <div class="mb-3">
        <div class="d-flex align-center justify-space-between mb-2">
          <span class="text-caption font-weight-medium">Origin-Destination Pairs</span>
          <v-btn
            :icon="mdiRefresh"
            size="x-small"
            variant="outlined"
            :disabled="trafficStore.isLoading"
            @click="shufflePairs"
          />
        </div>
        <v-card variant="outlined" flat>
          <v-list density="compact" class="pa-0">
            <v-list-item v-for="(pair, index) in trafficStore.nodePairs" :key="index" class="px-3">
              <template #prepend>
                <span class="text-caption mr-2">{{ index + 1 }}.</span>
              </template>
              <v-list-item-title class="text-caption">
                {{ pair.origin }} → {{ pair.destination }}
              </v-list-item-title>
            </v-list-item>
          </v-list>
        </v-card>
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
                v-for="edge in trafficStore.removedEdgesArray"
                :key="`${edge.u}-${edge.v}`"
                class="px-3"
              >
                <v-list-item-title class="text-caption">
                  {{ edge.u }} → {{ edge.v }}
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
              No edges removed. Click on edges in the map to remove them.
            </div>
          </v-card>
        </v-expand-transition>
      </div>

      <!-- Calculate Button -->
      <v-btn
        block
        variant="outlined"
        :prepend-icon="mdiCalculator"
        :disabled="trafficStore.isCalculating || trafficStore.nodePairs.length === 0"
        @click="calculateRoutes"
      >
        Calculate Routes
      </v-btn>

      <!-- Results Summary -->
      <div v-if="trafficStore.hasCalculatedRoutes" class="mt-3">
        <v-card variant="outlined" flat>
          <v-card-text class="pa-3">
            <div class="text-caption mb-2">
              Calculated {{ trafficStore.comparisons.length }} route comparisons
            </div>
            <div class="text-caption text-medium-emphasis">
              <strong>Legend:</strong>
              <ul class="ml-4 mt-1">
                <li>Faded paths: Original routes</li>
                <li>Bright paths: New routes (with edges removed)</li>
                <li>Black dashed: Removed edges</li>
              </ul>
            </div>
          </v-card-text>
        </v-card>
      </div>
    </v-card-text>
  </v-card>
</template>

<style scoped>
.traffic-analysis-panel {
  position: absolute;
  top: 80px;
  left: 320px;
  width: 400px;
  max-height: calc(100vh - 100px);
  overflow-y: auto;
  z-index: 1000;
  background-color: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
}

.border-b-sm {
  border-bottom: 1px solid rgba(0, 0, 0, 0.12);
}
</style>
