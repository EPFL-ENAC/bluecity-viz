<script setup lang="ts">
import { ref } from 'vue'
import { useLayersStore } from '@/stores/layers'
import {
  mdiChevronDown,
  mdiChevronRight,
  mdiPlus,
  mdiClose,
  mdiShare,
  mdiRadioboxMarked,
  mdiRadioboxBlank,
  mdiPencil,
  mdiCheck,
  mdiCancel
} from '@mdi/js'

// Use the layers store
const layersStore = useLayersStore()
layersStore.initializeInvestigations()

// Share functionality
const showShareDialog = ref(false)
const shareUrl = ref('')
const copySuccess = ref(false)
const investigationToShare = ref<string | null>(null)

// Edit functionality
const editingProject = ref<string | null>(null)
const editingInvestigation = ref<string | null>(null)
const editProjectName = ref('')
const editInvestigationName = ref('')

// Create new project functionality
const creatingNewProject = ref(false)
const newProjectName = ref('')

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

// Edit functions
function startEditingProject(projectId: string, currentName: string) {
  editingProject.value = projectId
  editProjectName.value = currentName
}

function cancelProjectEdit() {
  editingProject.value = null
  editProjectName.value = ''
}

function saveProjectEdit() {
  if (editingProject.value && editProjectName.value.trim()) {
    const project = layersStore.projects.find((p) => p.id === editingProject.value)
    if (project) {
      project.name = editProjectName.value.trim()
    }
    editingProject.value = null
    editProjectName.value = ''
  }
}

function startEditingInvestigation(investigationId: string, currentName: string) {
  editingInvestigation.value = investigationId
  editInvestigationName.value = currentName
}

function cancelInvestigationEdit() {
  editingInvestigation.value = null
  editInvestigationName.value = ''
}

function saveInvestigationEdit() {
  if (editingInvestigation.value && editInvestigationName.value.trim()) {
    const investigation = layersStore.findInvestigation(editingInvestigation.value)
    if (investigation) {
      investigation.name = editInvestigationName.value.trim()
    }
    editingInvestigation.value = null
    editInvestigationName.value = ''
  }
}

// Create new project functions
function startCreatingProject() {
  creatingNewProject.value = true
  newProjectName.value = 'New Project'
}

function cancelProjectCreation() {
  creatingNewProject.value = false
  newProjectName.value = ''
}

function saveNewProject() {
  if (newProjectName.value.trim()) {
    layersStore.createProject(newProjectName.value.trim())
    creatingNewProject.value = false
    newProjectName.value = ''
  }
}
</script>

<template>
  <v-card flat class="d-flex flex-column">
    <v-card-text class="flex-grow-1 overflow-y-auto pa-2">
      <!-- Create New Project -->
      <div v-if="creatingNewProject" class="mb-2">
        <v-card variant="outlined" class="pa-3">
          <div class="d-flex align-center">
            <v-text-field
              v-model="newProjectName"
              variant="outlined"
              density="compact"
              hide-details
              placeholder="Project name"
              class="mr-2"
              autofocus
              @keyup.enter="saveNewProject"
              @keyup.escape="cancelProjectCreation"
            />
            <v-btn
              :icon="mdiCheck"
              size="small"
              variant="text"
              color="success"
              @click="saveNewProject"
            />
            <v-btn
              :icon="mdiCancel"
              size="small"
              variant="text"
              color="error"
              @click="cancelProjectCreation"
            />
          </div>
        </v-card>
      </div>

      <!-- Add Project Button -->
      <div v-if="!creatingNewProject" class="mb-2">
        <v-btn variant="outlined" color="primary" block @click="startCreatingProject">
          <v-icon :icon="mdiPlus" class="mr-2" />
          New Project
        </v-btn>
      </div>

      <!-- Projects List -->
      <div v-for="project in layersStore.projects" :key="project.id" class="mb-2">
        <v-card variant="flat">
          <!-- Project Header -->
          <div class="d-flex align-center justify-space-between">
            <div class="d-flex align-center flex-grow-1">
              <v-icon
                class="mr-1"
                style="cursor: pointer"
                @click="layersStore.toggleProject(project.id)"
              >
                {{ project.expanded ? mdiChevronDown : mdiChevronRight }}
              </v-icon>

              <!-- Project Name - Editable -->
              <div v-if="editingProject === project.id" class="d-flex align-center flex-grow-1">
                <v-text-field
                  v-model="editProjectName"
                  variant="outlined"
                  density="compact"
                  hide-details
                  class="mr-2"
                  @keyup.enter="saveProjectEdit"
                  @keyup.escape="cancelProjectEdit"
                />
                <v-btn
                  :icon="mdiCheck"
                  size="x-small"
                  variant="text"
                  color="success"
                  @click="saveProjectEdit"
                />
                <v-btn
                  :icon="mdiCancel"
                  size="x-small"
                  variant="text"
                  color="error"
                  @click="cancelProjectEdit"
                />
              </div>

              <!-- Project Name - Display -->
              <span
                v-else
                class="text-subtitle-1 font-weight-medium flex-grow-1"
                style="cursor: pointer"
                @click="layersStore.toggleProject(project.id)"
              >
                {{ project.name }}
              </span>
            </div>

            <div class="d-flex align-center">
              <v-btn
                v-if="editingProject !== project.id"
                :icon="mdiPencil"
                size="small"
                variant="text"
                class="mr-1"
                @click="startEditingProject(project.id, project.name)"
              />
              <v-btn
                :icon="mdiPlus"
                size="small"
                variant="text"
                class="mr-1"
                @click="layersStore.saveCurrentState(project.id)"
              />
              <v-btn
                v-if="editingProject !== project.id"
                :icon="mdiClose"
                size="small"
                variant="text"
                @click="layersStore.removeProject(project.id)"
              />
            </div>
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
                    <div class="d-flex align-center flex-grow-1">
                      <v-icon
                        :icon="
                          layersStore.activeInvestigationId === investigation.id
                            ? mdiRadioboxMarked
                            : mdiRadioboxBlank
                        "
                        size="small"
                        class="mr-2"
                        :color="
                          layersStore.activeInvestigationId === investigation.id
                            ? 'primary'
                            : 'grey'
                        "
                      />
                      <div class="flex-grow-1">
                        <!-- Investigation Name - Editable -->
                        <div
                          v-if="editingInvestigation === investigation.id"
                          class="d-flex align-center"
                        >
                          <v-text-field
                            v-model="editInvestigationName"
                            variant="outlined"
                            density="compact"
                            hide-details
                            class="mr-2 investigation-edit-field"
                            @keyup.enter="saveInvestigationEdit"
                            @keyup.escape="cancelInvestigationEdit"
                          />
                          <v-btn
                            :icon="mdiCheck"
                            size="x-small"
                            variant="text"
                            color="success"
                            @click="saveInvestigationEdit"
                          />
                          <v-btn
                            :icon="mdiCancel"
                            size="x-small"
                            variant="text"
                            color="error"
                            @click="cancelInvestigationEdit"
                          />
                        </div>

                        <!-- Investigation Name - Display -->
                        <div v-else class="text-body-2 font-weight-medium">
                          {{ investigation.name }}
                        </div>

                        <div
                          v-if="editingInvestigation !== investigation.id"
                          class="text-caption text-medium-emphasis"
                        >
                          {{ investigation.selectedSources.length }} sources,
                          {{ investigation.selectedLayers.length }} layers
                        </div>
                      </div>
                    </div>
                    <div class="d-flex align-center">
                      <v-btn
                        :icon="mdiShare"
                        size="x-small"
                        variant="text"
                        density="compact"
                        class="mr-3"
                        @click.stop="handleShare(investigation.id)"
                      >
                      </v-btn>
                      <v-btn
                        v-if="editingInvestigation !== investigation.id"
                        :icon="mdiPencil"
                        size="x-small"
                        variant="text"
                        density="compact"
                        class="mr-3"
                        @click.stop="
                          startEditingInvestigation(investigation.id, investigation.name)
                        "
                      />
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
  border-color: #e0e0e0;
}

.investigation-card:hover {
  background-color: rgb(var(--v-theme-surface-variant));
}

.active-investigation {
  background-color: rgb(var(--v-theme-primary-container)) !important;
  border-color: rgb(var(--v-theme-primary)) !important;
}

.cursor-pointer {
  cursor: pointer;
}

.investigation-edit-field :deep(.v-field__input) {
  font-size: 0.875rem;
  font-weight: 500;
  line-height: 1.25rem;
}
</style>
