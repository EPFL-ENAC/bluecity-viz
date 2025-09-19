<script setup lang="ts">
import AddSourceDialog from '@/components/panels/AddSourceDialog.vue'
import { useLayersStore } from '@/stores/layers'
import { ref } from 'vue'
import { mdiPlus, mdiChevronDown, mdiChevronRight, mdiClose } from '@mdi/js'

// Use the layers store
const layersStore = useLayersStore()

// Local state for the component (only UI state)
const dataSetsExpanded = ref(true)
const analyticsExpanded = ref(true)
const visualizationsExpanded = ref(true)
const addSourceDialog = ref(false)
const addAnalyticsDialog = ref(false)
const addVisualizationsDialog = ref(false)
</script>

<template>
  <v-card flat class="d-flex flex-column">
    <v-card-title class="flex-shrink-0 text-center pa-2">
      <h6 class="w-100">RESOURCES</h6>
    </v-card-title>
    <v-card-text class="flex-grow-1 d-flex flex-column overflow-hidden">
      <!-- Data Sets Section -->
      <div class="mb-4 flex-shrink-0">
        <!-- Data Sets Header with Add Button -->
        <div class="d-flex align-center justify-between mb-3">
          <v-btn
            variant="text"
            class="pa-0 text-subtitle-1"
            :icon="dataSetsExpanded ? mdiChevronDown : mdiChevronRight"
            @click="dataSetsExpanded = !dataSetsExpanded"
          >
          </v-btn>
          Datasets
          <v-btn :icon="mdiPlus" variant="text" size="small" @click="addSourceDialog = true" />
        </div>

        <!-- Data Sets List (Expandable) -->
        <v-expand-transition>
          <div v-show="dataSetsExpanded">
            <div
              v-if="layersStore.availableResourceSources.length === 0"
              class="text-center py-4 text--secondary"
            >
              <p>No data sets added yet</p>
              <p class="text-caption">Click the + button to add data sources</p>
            </div>
            <div v-else class="space-y-2">
              <v-card
                v-for="source in layersStore.availableResourceSourceObjects"
                :key="source.id"
                density="compact"
                class="mb-1"
              >
                <v-card-text class="py-1 px-2">
                  <div class="d-flex align-center justify-between">
                    <div class="flex-grow-1">
                      <div class="d-flex align-center">
                        <v-switch
                          :model-value="layersStore.isSourceEnabled(source.id)"
                          class="ma-2 mr-4"
                          color="primary"
                          hide-details
                          density="compact"
                          @update:model-value="
                            (enabled) => layersStore.toggleSource(source.id, enabled)
                          "
                        />
                        <div>
                          <h6 class="text-subtitle-2 mb-0">{{ source.label }}</h6>
                          <p class="text-caption text--secondary mb-0">
                            {{ layersStore.getLayersBySource(source.id).length }} layers available
                          </p>
                        </div>
                      </div>
                    </div>
                    <v-btn
                      :icon="mdiClose"
                      variant="text"
                      size="small"
                      density="compact"
                      @click="layersStore.removeSource(source.id)"
                    />
                  </div>
                </v-card-text>
              </v-card>
            </div>
          </div>
        </v-expand-transition>
      </div>

      <!-- Analytics Tools Section -->
      <div class="mb-4 flex-shrink-0">
        <!-- Analytics Tools Header with Add Button -->
        <div class="d-flex align-center justify-between mb-3">
          <v-btn
            variant="text"
            class="pa-0 text-subtitle-1"
            :icon="analyticsExpanded ? mdiChevronDown : mdiChevronRight"
            @click="analyticsExpanded = !analyticsExpanded"
          >
          </v-btn>
          Analytics Tools
          <v-btn :icon="mdiPlus" variant="text" size="small" @click="addAnalyticsDialog = true" />
        </div>

        <!-- Analytics Tools List (Expandable) -->
        <v-expand-transition>
          <div v-show="analyticsExpanded">
            <div class="space-y-2">
              <v-card
                v-for="tool in [
                  {
                    id: 'correlation',
                    label: 'Correlation Analysis',
                    description: 'Analyze relationships between datasets'
                  },
                  {
                    id: 'clustering',
                    label: 'Spatial Clustering',
                    description: 'Identify spatial patterns and clusters'
                  }
                ]"
                :key="tool.id"
                density="compact"
                class="mb-1"
              >
                <v-card-text class="py-1 px-2">
                  <div class="d-flex align-center justify-between">
                    <div class="flex-grow-1">
                      <div class="d-flex align-center">
                        <v-switch
                          :model-value="false"
                          class="ma-2 mr-4"
                          color="primary"
                          hide-details
                          density="compact"
                        />
                        <div>
                          <h6 class="text-body-2 mb-0">{{ tool.label }}</h6>
                          <p class="text-caption text--secondary mb-0">
                            {{ tool.description }}
                          </p>
                        </div>
                      </div>
                    </div>
                    <v-btn
                      :icon="mdiClose"
                      variant="text"
                      size="small"
                      density="compact"
                      disabled
                    />
                  </div>
                </v-card-text>
              </v-card>
            </div>
          </div>
        </v-expand-transition>
      </div>

      <!-- Visualizations Section -->
      <div class="mb-4 flex-shrink-0">
        <!-- Visualizations Header with Add Button -->
        <div class="d-flex align-center justify-between mb-3">
          <v-btn
            variant="text"
            class="pa-0 text-subtitle-1"
            :icon="visualizationsExpanded ? mdiChevronDown : mdiChevronRight"
            @click="visualizationsExpanded = !visualizationsExpanded"
          >
          </v-btn>
          Visualizations
          <v-btn
            :icon="mdiPlus"
            variant="text"
            size="small"
            @click="addVisualizationsDialog = true"
          />
        </div>

        <!-- Visualizations List (Expandable) -->
        <v-expand-transition>
          <div v-show="visualizationsExpanded">
            <div class="space-y-2">
              <v-card
                v-for="viz in [
                  {
                    id: 'heatmap',
                    label: 'Heat Map',
                    description: 'Display data intensity with color gradients'
                  },
                  {
                    id: 'choropleth',
                    label: 'Choropleth Map',
                    description: 'Show data variations across regions'
                  },
                  {
                    id: 'scatter',
                    label: 'Scatter Plot',
                    description: 'Plot relationships between variables'
                  }
                ]"
                :key="viz.id"
                density="compact"
                class="mb-1"
              >
                <v-card-text class="py-1 px-2">
                  <div class="d-flex align-center justify-between">
                    <div class="flex-grow-1">
                      <div class="d-flex align-center">
                        <v-switch
                          :model-value="false"
                          class="ma-2 mr-4"
                          color="primary"
                          hide-details
                          density="compact"
                        />
                        <div>
                          <h6 class="text-body-2 mb-0">{{ viz.label }}</h6>
                          <p class="text-caption text--secondary mb-0">
                            {{ viz.description }}
                          </p>
                        </div>
                      </div>
                    </div>
                    <v-btn
                      :icon="mdiClose"
                      variant="text"
                      size="small"
                      density="compact"
                      disabled
                    />
                  </div>
                </v-card-text>
              </v-card>
            </div>
          </div>
        </v-expand-transition>
      </div>
    </v-card-text>

    <!-- Add Source Dialog -->
    <AddSourceDialog v-model="addSourceDialog" />
  </v-card>
</template>
