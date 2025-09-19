<script setup lang="ts">
import AddSourceDialog from '@/components/panels/AddSourceDialog.vue'
import { useLayersStore } from '@/stores/layers'
import { ref } from 'vue'
import {
  mdiPlus,
  mdiChevronDown,
  mdiChevronRight,
  mdiClose,
  mdiCheckboxMarked,
  mdiCheckboxBlankOutline
} from '@mdi/js'

// Use the layers store
const layersStore = useLayersStore()

// Local state for the component (only UI state)
const dataSetsExpanded = ref(true)
const analyticsExpanded = ref(true)
const visualizationsExpanded = ref(true)
const addSourceDialog = ref(false)
const addAnalyticsDialog = ref(false)
const addVisualizationsDialog = ref(false)

// State for placeholder items
const enabledTools = ref(new Set<string>())
const enabledVisualizations = ref(new Set<string>())

// Functions for placeholder interactions
const toggleTool = (toolId: string) => {
  if (enabledTools.value.has(toolId)) {
    enabledTools.value.delete(toolId)
  } else {
    enabledTools.value.add(toolId)
  }
}

const toggleVisualization = (vizId: string) => {
  if (enabledVisualizations.value.has(vizId)) {
    enabledVisualizations.value.delete(vizId)
  } else {
    enabledVisualizations.value.add(vizId)
  }
}
</script>

<template>
  <v-card flat class="d-flex flex-column">
    <v-card-text class="flex-grow-1 d-flex flex-column overflow-hidden pa-2">
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
            <div v-else>
              <v-card
                v-for="source in layersStore.availableResourceSourceObjects"
                :key="source.id"
                :class="[
                  'source-card mb-1 cursor-pointer',
                  { 'active-source': layersStore.isSourceEnabled(source.id) }
                ]"
                variant="outlined"
                density="compact"
                @click="
                  layersStore.toggleSource(source.id, !layersStore.isSourceEnabled(source.id))
                "
              >
                <v-card-text class="py-2 px-3">
                  <div class="d-flex align-center justify-space-between w-100">
                    <div class="d-flex align-center flex-grow-1">
                      <v-icon
                        :icon="
                          layersStore.isSourceEnabled(source.id)
                            ? mdiCheckboxMarked
                            : mdiCheckboxBlankOutline
                        "
                        size="small"
                        class="mr-2"
                        :color="layersStore.isSourceEnabled(source.id) ? 'primary' : 'grey'"
                      />
                      <div class="flex-grow-1">
                        <div class="text-body-2 font-weight-medium">{{ source.label }}</div>
                        <div class="text-caption text-medium-emphasis">
                          {{ layersStore.getLayersBySource(source.id).length }} layers available
                        </div>
                      </div>
                    </div>
                    <div class="d-flex align-center ml-2">
                      <v-btn
                        :icon="mdiClose"
                        size="x-small"
                        variant="text"
                        density="compact"
                        @click.stop="layersStore.removeSource(source.id)"
                      >
                      </v-btn>
                    </div>
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
              :class="[
                'tool-card mb-1 cursor-pointer',
                { 'active-tool': enabledTools.has(tool.id) }
              ]"
              variant="outlined"
              density="compact"
              @click="toggleTool(tool.id)"
            >
              <v-card-text class="py-2 px-3">
                <div class="d-flex align-center justify-space-between w-100">
                  <div class="d-flex align-center flex-grow-1">
                    <v-icon
                      :icon="
                        enabledTools.has(tool.id) ? mdiCheckboxMarked : mdiCheckboxBlankOutline
                      "
                      size="small"
                      class="mr-2"
                      :color="enabledTools.has(tool.id) ? 'primary' : 'grey'"
                    />
                    <div class="flex-grow-1">
                      <div class="text-body-2 font-weight-medium">{{ tool.label }}</div>
                      <div class="text-caption text-medium-emphasis">
                        {{ tool.description }}
                      </div>
                    </div>
                  </div>
                  <div class="d-flex align-center">
                    <v-btn
                      :icon="mdiClose"
                      size="x-small"
                      variant="text"
                      density="compact"
                      @click.stop="enabledTools.delete(tool.id)"
                    >
                    </v-btn>
                  </div>
                </div>
              </v-card-text>
            </v-card>
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
              :class="[
                'viz-card mb-1 cursor-pointer',
                { 'active-viz': enabledVisualizations.has(viz.id) }
              ]"
              variant="outlined"
              density="compact"
              @click="toggleVisualization(viz.id)"
            >
              <v-card-text class="py-2 px-3">
                <div class="d-flex align-center justify-space-between w-100">
                  <div class="d-flex align-center flex-grow-1">
                    <v-icon
                      :icon="
                        enabledVisualizations.has(viz.id)
                          ? mdiCheckboxMarked
                          : mdiCheckboxBlankOutline
                      "
                      size="small"
                      class="mr-2"
                      :color="enabledVisualizations.has(viz.id) ? 'primary' : 'grey'"
                    />
                    <div class="flex-grow-1">
                      <div class="text-body-2 font-weight-medium">{{ viz.label }}</div>
                      <div class="text-caption text-medium-emphasis">
                        {{ viz.description }}
                      </div>
                    </div>
                  </div>
                  <div class="d-flex align-center">
                    <v-btn
                      :icon="mdiClose"
                      size="x-small"
                      variant="text"
                      density="compact"
                      @click.stop="enabledVisualizations.delete(viz.id)"
                    >
                    </v-btn>
                  </div>
                </div>
              </v-card-text>
            </v-card>
          </div>
        </v-expand-transition>
      </div>
    </v-card-text>

    <!-- Add Source Dialog -->
    <AddSourceDialog v-model="addSourceDialog" />
  </v-card>
</template>

<style scoped>
.panel-header {
  background-color: #fafafa;
  border-bottom: 1px solid #e0e0e0;
}

.source-card,
.tool-card,
.viz-card {
  transition: all 0.2s ease;
}

.source-card:hover,
.tool-card:hover,
.viz-card:hover {
  background-color: #f5f5f5;
}

.active-source,
.active-tool,
.active-viz {
  background-color: #e3f2fd !important;
  border-color: #2196f3 !important;
}

.cursor-pointer {
  cursor: pointer;
}
</style>
