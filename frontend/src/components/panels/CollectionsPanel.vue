<script setup lang="ts">
import { useLayersStore } from '@/stores/layers'
import { mdiChevronDown, mdiChevronRight, mdiPlus, mdiClose } from '@mdi/js'

// Use the layers store
const layersStore = useLayersStore()
layersStore.initializeInvestigations()
</script>

<template>
  <v-card flat class="d-flex flex-column">
    <v-card-title class="flex-shrink-0 text-center pa-2">
      <h6 class="w-100">COLLECTIONS</h6>
    </v-card-title>
    <v-card-text class="flex-grow-1 overflow-y-auto py-1 px-2">
      <!-- Projects List -->
      <div v-for="project in layersStore.projects" :key="project.id" class="mb-2">
        <v-card variant="flat" class="pa-4">
          <!-- Project Header -->
          <div class="d-flex align-center justify-space-between">
            <div
              class="d-flex align-center flex-grow-1"
              style="cursor: pointer"
              @click="layersStore.toggleProject(project.id)"
            >
              <v-icon size="small" class="mr-1">
                {{ project.expanded ? mdiChevronDown : mdiChevronRight }}
              </v-icon>
              <span class="text-subtitle-1 font-weight-medium">{{ project.name }}</span>
            </div>
            <v-btn
              :icon="mdiPlus"
              size="x-small"
              variant="text"
              class="ml-1"
              @click="layersStore.saveCurrentState(project.id)"
            >
            </v-btn>
          </div>

          <!-- Investigations List -->
          <v-expand-transition>
            <div v-show="project.expanded" class="mt-2">
              <v-radio-group
                :model-value="layersStore.activeInvestigationId"
                density="compact"
                class="mb-0"
                @update:model-value="layersStore.switchToInvestigation($event)"
              >
                <v-radio
                  v-for="investigation in project.investigations"
                  :key="investigation.id"
                  :value="investigation.id"
                  density="compact"
                  class="mb-1"
                >
                  <template #label>
                    <div class="d-flex align-center justify-space-between w-100">
                      <div class="flex-grow-1">
                        <div class="text-body-2">{{ investigation.name }}</div>
                        <div class="text-caption text-medium-emphasis">
                          {{ investigation.selectedSources.length }} sources,
                          {{ investigation.selectedLayers.length }} layers
                        </div>
                      </div>
                      <v-btn
                        :icon="mdiClose"
                        size="x-small"
                        variant="text"
                        density="compact"
                        class="ml-2"
                        @click.stop="layersStore.removeInvestigation(investigation.id)"
                      >
                      </v-btn>
                    </div>
                  </template>
                </v-radio>
              </v-radio-group>
            </div>
          </v-expand-transition>
        </v-card>
      </div>
    </v-card-text>
  </v-card>
</template>
