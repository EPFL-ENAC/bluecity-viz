<script setup lang="ts">
import { ref, onMounted, watch, inject, type Ref } from 'vue'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { generateRandomPairs, recalculateRoutes } from '@/services/trafficAnalysis'
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
const mapRef = inject<Ref<any>>('mapRef')

onMounted(async () => {
  await shufflePairs()
  if (mapRef?.value?.trafficAnalysisMap && trafficStore.isOpen) {
    mapRef.value.trafficAnalysisMap.addGraphEdgesLayerFromTiles()
  }
})

watch(
  () => trafficStore.isOpen,
  (isOpen) => {
    if (!mapRef?.value?.trafficAnalysisMap) return

    if (isOpen) {
      mapRef.value.trafficAnalysisMap.addGraphEdgesLayerFromTiles()
      mapRef.value.trafficAnalysisMap.attachEdgeClickListener(handleEdgeClick)
    } else {
      mapRef.value.trafficAnalysisMap.removeGraphEdgesLayer()
      mapRef.value.trafficAnalysisMap.clearRoutes()
      mapRef.value.trafficAnalysisMap.detachEdgeClickListener()
    }
  }
)

watch(
  () => trafficStore.removedEdgesArray,
  (removedEdges) => {
    if (mapRef?.value?.trafficAnalysisMap) {
      mapRef.value.trafficAnalysisMap.updateRemovedEdges(removedEdges)
    }
  },
  { deep: true }
)

watch(
  () => [trafficStore.originalEdgeUsage, trafficStore.newEdgeUsage],
  ([originalUsage, newUsage]) => {
    if (originalUsage.length > 0 && mapRef?.value?.trafficAnalysisMap) {
      mapRef.value.trafficAnalysisMap.visualizeEdgeUsage(originalUsage, newUsage)
    }
  },
  { deep: true }
)

function handleEdgeClick(u: number, v: number) {
  trafficStore.addRemovedEdge(u, v)
}

async function shufflePairs() {
  trafficStore.isLoading = true
  loadingMessage.value = 'Generating random pairs...'
  try {
    const pairs = await generateRandomPairs(100, undefined, 1)
    trafficStore.setNodePairs(pairs)
    trafficStore.clearResults()
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
    trafficStore.setEdgeUsage(result.original_edge_usage, result.new_edge_usage)
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
      <!-- Regenerate Pairs -->
      <div class="mb-3">
        <v-btn
          block
          variant="outlined"
          :prepend-icon="mdiRefresh"
          :disabled="trafficStore.isLoading"
          @click="shufflePairs"
        >
          Generate New Pairs
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
      <!-- Loading State -->
      <v-progress-linear
        v-if="trafficStore.isLoading || trafficStore.isCalculating"
        indeterminate
        class="my-6"
      />
      <div v-if="trafficStore.isLoading || trafficStore.isCalculating" class="text-center mb-3">
        <p class="text-caption text-medium-emphasis">{{ loadingMessage }}</p>
      </div>
      <!-- Results Summary -->
      <div v-if="trafficStore.hasCalculatedRoutes" class="mt-3">
        <v-card variant="outlined" flat>
          <v-card-text class="pa-3">
            <div class="text-caption mb-2">
              Original: {{ trafficStore.originalEdgeUsage.length }} edges used
            </div>
            <div class="text-caption mb-2">
              After removal: {{ trafficStore.newEdgeUsage.length }} edges used
            </div>
            <div class="text-caption text-medium-emphasis">
              <strong>Legend:</strong>
              <ul class="ml-4 mt-1">
                <li>Blue edges: Original routes (opacity = frequency)</li>
                <li>Orange edges: New routes (opacity = frequency)</li>
                <li>Red dashed: Removed edges</li>
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
