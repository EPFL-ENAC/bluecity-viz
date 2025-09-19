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
const investigationToShare = ref<string | null>(null)

function handleShare(investigationId: string) {
  // Switch to the investigation first to ensure it's active
  layersStore.switchToInvestigation(investigationId)

  if (!layersStore.activeInvestigation) {
    return
  }

  investigationToShare.value = investigationId
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
    <v-card-text class="flex-grow-1 overflow-y-auto pa-2">
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
            <div v-show="project.expanded" class="mt-2">
              <v-card
                v-for="investigation in project.investigations"
                :key="investigation.id"
                :class="[
                  'investigation-card mb-1 cursor-pointer',
                  { 'active-investigation': layersStore.activeInvestigationId === investigation.id }
                ]"
                variant="outlined"
                density="compact"
                @click="layersStore.switchToInvestigation(investigation.id)"
              >
                <v-card-text class="py-2 px-3">
                  <div class="d-flex align-center justify-space-between w-100">
                    <div class="flex-grow-1">
                      <div class="text-body-2 font-weight-medium">{{ investigation.name }}</div>
                      <div class="text-caption text-medium-emphasis">
                        {{ investigation.selectedSources.length }} sources,
                        {{ investigation.selectedLayers.length }} layers
                      </div>
                    </div>
                    <div class="d-flex align-center">
                      <v-btn
                        :icon="mdiShare"
                        size="x-small"
                        variant="text"
                        density="compact"
                        class="mr-1"
                        @click.stop="handleShare(investigation.id)"
                      >
                      </v-btn>
                      <v-btn
                        :icon="mdiClose"
                        size="x-small"
                        variant="text"
                        density="compact"
                        @click.stop="layersStore.removeInvestigation(investigation.id)"
                      >
                      </v-btn>
                    </div>
                  </div>
                </v-card-text>
              </v-card>
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
            Share investigation "{{
              investigationToShare ? layersStore.findInvestigation(investigationToShare)?.name : ''
            }}" with others using this URL:
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

<style scoped>
.panel-header {
  background-color: #fafafa;
  border-bottom: 1px solid #e0e0e0;
}

.investigation-card {
  transition: all 0.2s ease;
}

.investigation-card:hover {
  background-color: #f5f5f5;
}

.active-investigation {
  background-color: #e3f2fd !important;
  border-color: #2196f3 !important;
}

.cursor-pointer {
  cursor: pointer;
}
</style>
