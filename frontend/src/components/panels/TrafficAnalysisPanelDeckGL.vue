<script setup lang="ts">
import { ref, onMounted } from 'vue'
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

onMounted(async () => {
  await shufflePairs()
})

async function shufflePairs() {
  trafficStore.isLoading = true
  loadingMessage.value = 'Generating random pairs...'
  try {
    const pairs = await generateRandomPairs(1000, undefined, 3)
    trafficStore.setNodePairs(pairs)
    trafficStore.clearResults()
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
  <!-- Control Panel -->
  <v-card v-if="trafficStore.isOpen" class="traffic-analysis-panel-deckgl" variant="outlined" flat>
    <v-card-title class="d-flex align-center justify-space-between pa-3 border-b-sm">
      <span class="text-subtitle-1">TRAFFIC ANALYSIS (DECK.GL)</span>
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
        :disabled="trafficStore.isCalculating || trafficStore.nodePairs.length === 0"
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

      <!-- Info Text -->
      <div class="mt-3 text-caption text-medium-emphasis">
        <p>Using Deck.gl for visualization:</p>
        <ul class="ml-4">
          <li>Click edges to remove them</li>
          <li>Blue: Original routes</li>
          <li>Orange: Rerouted traffic</li>
          <li>Red: Removed edges</li>
        </ul>
      </div>
    </v-card-text>
  </v-card>
</template>

<style scoped>
.traffic-analysis-panel-deckgl {
  position: absolute;
  top: 80px;
  left: 320px;
  width: 350px;
  max-height: calc(100vh - 100px);
  overflow-y: auto;
  z-index: 1000;
  background-color: rgba(var(--v-theme-surface), 0.95);
  backdrop-filter: blur(8px);
}
</style>
