<script setup lang="ts">
import AddSourceDialog from '@/components/panels/AddSourceDialog.vue'
import { useLayersStore } from '@/stores/layers'
import { ref } from 'vue'
import { mdiPlus, mdiChevronDown, mdiChevronRight, mdiClose } from '@mdi/js'

// Use the layers store
const layersStore = useLayersStore()

// Local state for the component (only UI state)
const dataSetsExpanded = ref(true)
const addSourceDialog = ref(false)
</script>

<template>
  <v-card flat class="d-flex flex-column">
    <v-card-title class="flex-shrink-0 text-center pa-2">
      <h6 class="w-100">RESOURCES</h6>
    </v-card-title>
    <v-card-text class="flex-grow-1 d-flex flex-column overflow-hidden">
      <!-- Data Sets Section -->
      <div class="mb-6 flex-shrink-0">
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
              v-if="layersStore.selectedSources.length === 0"
              class="text-center py-4 text--secondary"
            >
              <p>No data sets added yet</p>
              <p class="text-caption">Click the + button to add data sources</p>
            </div>
            <div v-else class="space-y-2">
              <v-card
                v-for="source in layersStore.selectedSourceObjects"
                :key="source.id"
                density="compact"
                class="mb-2"
              >
                <v-card-text class="py-2">
                  <div class="d-flex align-center justify-between">
                    <div class="flex-grow-1">
                      <div class="d-flex align-center">
                        <v-switch
                          :model-value="layersStore.isSourceEnabled(source.id)"
                          class="mr-3"
                          color="primary"
                          hide-details
                          @update:model-value="
                            (enabled) => layersStore.toggleSource(source.id, enabled)
                          "
                        />
                        <div>
                          <h6 class="text-subtitle-2">{{ source.label }}</h6>
                          <p class="text-caption text--secondary">
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
    </v-card-text>

    <!-- Add Source Dialog -->
    <AddSourceDialog v-model="addSourceDialog" />
  </v-card>
</template>
