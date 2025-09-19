<script setup lang="ts">
import { ref } from 'vue'
import { useLayersStore } from '@/stores/layers'
import { mdiChevronDown, mdiChevronRight, mdiPlus, mdiClose, mdiShare } from '@mdi/js'

// Use the layers store
const layersStore = useLayersStore()
layersStore.initializeInvestigations()

// Share functionality
const showShareDialog = ref(false)
const shareUrl = ref('')
const copySuccess = ref(false)

function handleShare() {
  if (!layersStore.activeInvestigation) {
    return
  }

  shareUrl.value = layersStore.generateShareableUrl()
  showShareDialog.value = true
  copySuccess.value = false
}

async function copyToClipboard() {
  try {
    await navigator.clipboard.writeText(shareUrl.value)
    copySuccess.value = true
    setTimeout(() => {
      copySuccess.value = false
    }, 2000)
  } catch (error) {
    console.warn('Failed to copy to clipboard:', error)
    // Fallback for older browsers
    const textArea = document.createElement('textarea')
    textArea.value = shareUrl.value
    document.body.appendChild(textArea)
    textArea.select()
    document.execCommand('copy')
    document.body.removeChild(textArea)
    copySuccess.value = true
    setTimeout(() => {
      copySuccess.value = false
    }, 2000)
  }
}
</script>

<template>
  <v-card flat class="d-flex flex-column">
    <v-card-title class="flex-shrink-0 text-center pa-2 pb-6">
      <div class="d-flex align-center justify-space-between w-100">
        <div></div>
        <!-- Spacer -->
        <h6>COLLECTIONS</h6>
        <v-btn
          :icon="mdiShare"
          size="small"
          variant="text"
          :disabled="!layersStore.activeInvestigation"
          @click="handleShare"
        >
        </v-btn>
      </div>
    </v-card-title>
    <v-card-text class="flex-grow-1 overflow-y-auto">
      <!-- Projects List -->
      <div v-for="project in layersStore.projects" :key="project.id" class="mb-2">
        <v-card variant="flat">
          <!-- Project Header -->
          <div class="d-flex align-center justify-space-between">
            <div
              class="d-flex align-center flex-grow-1"
              style="cursor: pointer"
              @click="layersStore.toggleProject(project.id)"
            >
              <v-icon class="mr-1">
                {{ project.expanded ? mdiChevronDown : mdiChevronRight }}
              </v-icon>
              <span class="text-subtitle-1 font-weight-medium">{{ project.name }}</span>
            </div>
            <v-btn
              :icon="mdiPlus"
              size="small"
              variant="text"
              class="ml-1"
              @click="layersStore.saveCurrentState(project.id)"
            >
            </v-btn>
          </div>

          <!-- Investigations List -->
          <v-expand-transition>
            <div v-show="project.expanded" class="mt-2 w-100">
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
                  class="mb-1 mr-4"
                >
                  <template #label>
                    <div class="d-flex align-center justify-space-between w-100 px-4">
                      <div class="flex-grow-1">
                        <div class="text-body-2">{{ investigation.name }}</div>
                        <div class="text-caption text-medium-emphasis">
                          {{ investigation.selectedSources.length }} sources,
                          {{ investigation.selectedLayers.length }} layers
                        </div>
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
                  </template>
                </v-radio>
              </v-radio-group>
            </div>
          </v-expand-transition>
        </v-card>
      </div>
    </v-card-text>

    <!-- Share Dialog -->
    <v-dialog v-model="showShareDialog" max-width="500px">
      <v-card>
        <v-card-title class="text-h6">Share Investigation</v-card-title>
        <v-card-text>
          <p class="mb-4">
            Share your current investigation "{{ layersStore.activeInvestigation?.name }}" with
            others using this URL:
          </p>
          <v-text-field
            v-model="shareUrl"
            label="Shareable URL"
            readonly
            variant="outlined"
            density="compact"
            class="mb-3"
          >
            <template #append-inner>
              <v-btn
                :icon="copySuccess ? 'mdi-check' : 'mdi-content-copy'"
                size="small"
                variant="text"
                :color="copySuccess ? 'success' : 'primary'"
                @click="copyToClipboard"
              >
              </v-btn>
            </template>
          </v-text-field>
          <v-alert v-if="copySuccess" type="success" density="compact" class="mb-3">
            URL copied to clipboard!
          </v-alert>
          <p class="text-caption text-medium-emphasis">
            Anyone with this URL will be able to view your current investigation setup including
            selected sources and layers.
          </p>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn color="primary" @click="showShareDialog = false">Close</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>
