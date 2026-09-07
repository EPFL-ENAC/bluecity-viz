<script setup lang="ts">
import { computed, ref } from 'vue'
import { useLayersStore } from '@/stores/layers'
import BcIcon from '@/components/ui/BcIcon.vue'
import BcRow from '@/components/ui/BcRow.vue'
import ShareDialog from '@/components/dialogs/ShareDialog.vue'
import DeleteDialog from '@/components/dialogs/DeleteDialog.vue'

// Use the layers store. initializeInvestigations() is called once by HomeView.
const layersStore = useLayersStore()

// Share functionality
const showShareDialog = ref(false)
const shareUrl = ref('')

// Edit functionality
const editingProject = ref<string | null>(null)
const editingInvestigation = ref<string | null>(null)
const editProjectName = ref('')
const editInvestigationName = ref('')

// Create new project functionality
const creatingNewProject = ref(false)
const newProjectName = ref('')

// Delete confirmation functionality
const showDeleteDialog = ref(false)
const deleteType = ref<'project' | 'investigation'>('project')
const deleteTargetId = ref<string | null>(null)
const deleteTargetName = ref('')
const deleteTargetCount = ref(0)

// The project holding the active investigation, for the sub-line.
const activeProject = computed(() =>
  layersStore.projects.find((p) =>
    p.investigations.some((i) => i.id === layersStore.activeInvestigationId)
  )
)

const subLine = computed(() => {
  const inv = layersStore.activeInvestigation
  if (!inv) return ''
  const parts = [
    activeProject.value?.name,
    `${inv.selectedSources.length} sources`,
    `${inv.selectedLayers.length} layers`
  ].filter(Boolean)
  return parts.join(' · ')
})

function investigationMeta(inv: { selectedSources: string[]; selectedLayers: string[] }) {
  return `${inv.selectedSources.length} src · ${inv.selectedLayers.length} lyr`
}

function handleShare(investigationId: string) {
  // Switch to the investigation first to ensure it's active
  layersStore.switchToInvestigation(investigationId)

  if (!layersStore.activeInvestigation) {
    return
  }

  shareUrl.value = layersStore.generateShareableUrl()
  showShareDialog.value = true
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
  }
  cancelProjectEdit()
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
  }
  cancelInvestigationEdit()
}

// Create new project functions
function startCreatingProject() {
  creatingNewProject.value = true
  newProjectName.value = 'New project'
}

function cancelProjectCreation() {
  creatingNewProject.value = false
  newProjectName.value = ''
}

function saveNewProject() {
  if (newProjectName.value.trim()) {
    layersStore.createProject(newProjectName.value.trim())
  }
  cancelProjectCreation()
}

// Delete confirmation functions
function confirmDeleteProject(projectId: string) {
  const project = layersStore.projects.find((p) => p.id === projectId)
  if (!project) return

  // If project has no investigations, delete directly without confirmation
  if (project.investigations.length === 0) {
    layersStore.removeProject(projectId)
    return
  }

  deleteType.value = 'project'
  deleteTargetId.value = projectId
  deleteTargetName.value = project.name
  deleteTargetCount.value = project.investigations.length
  showDeleteDialog.value = true
}

function confirmDeleteInvestigation(investigationId: string) {
  const investigation = layersStore.findInvestigation(investigationId)
  if (!investigation) return

  deleteType.value = 'investigation'
  deleteTargetId.value = investigationId
  deleteTargetName.value = investigation.name
  deleteTargetCount.value = 0
  showDeleteDialog.value = true
}

function executeDelete() {
  if (!deleteTargetId.value) return

  if (deleteType.value === 'project') {
    layersStore.removeProject(deleteTargetId.value)
  } else {
    layersStore.removeInvestigation(deleteTargetId.value)
  }

  cancelDelete()
}

function cancelDelete() {
  showDeleteDialog.value = false
  deleteTargetId.value = null
  deleteTargetName.value = ''
  deleteTargetCount.value = 0
}

// Acting on the active investigation from the section header
function shareActive() {
  if (layersStore.activeInvestigationId) handleShare(layersStore.activeInvestigationId)
}

function editActive() {
  const inv = layersStore.activeInvestigation
  if (inv) startEditingInvestigation(inv.id, inv.name)
}

function deleteActive() {
  if (layersStore.activeInvestigationId)
    confirmDeleteInvestigation(layersStore.activeInvestigationId)
}
</script>

<template>
  <div class="section">
    <div class="section__head">
      <span class="bc-micro">Investigation</span>
      <span v-if="layersStore.activeInvestigation" class="section__actions">
        <button class="icon-btn" title="Share" @click="shareActive">
          <BcIcon name="share-2" :size="14" />
        </button>
        <button class="icon-btn" title="Rename" @click="editActive">
          <BcIcon name="edit-2" :size="14" />
        </button>
        <button class="icon-btn" title="Delete" @click="deleteActive">
          <BcIcon name="trash-2" :size="14" />
        </button>
      </span>
    </div>

    <div v-if="layersStore.activeInvestigation" class="section__title">
      {{ layersStore.activeInvestigation.name }}
    </div>
    <div v-else class="section__title">No investigation</div>
    <div v-if="subLine" class="section__sub">{{ subLine }}</div>

    <div class="tree">
      <template v-for="project in layersStore.projects" :key="project.id">
        <div class="project-row">
          <button class="icon-btn" @click="layersStore.toggleProject(project.id)">
            <BcIcon :name="project.expanded ? 'chevron-down' : 'chevron-right'" />
          </button>
          <input
            v-if="editingProject === project.id"
            v-model="editProjectName"
            class="inline-input"
            autofocus
            @keyup.enter="saveProjectEdit"
            @keyup.esc="cancelProjectEdit"
            @blur="saveProjectEdit"
          />
          <span
            v-else
            class="project-row__name"
            @dblclick="startEditingProject(project.id, project.name)"
            >{{ project.name }}</span
          >
          <span class="bc-meta">{{ project.investigations.length }}</span>
          <button
            class="icon-btn"
            title="Save the current state here"
            @click="layersStore.saveCurrentState(project.id)"
          >
            <BcIcon name="plus" />
          </button>
          <button class="icon-btn" title="Delete project" @click="confirmDeleteProject(project.id)">
            <BcIcon name="trash-2" />
          </button>
        </div>

        <template v-if="project.expanded">
          <BcRow
            v-for="inv in project.investigations"
            :key="inv.id"
            :check="false"
            :on="inv.id === layersStore.activeInvestigationId"
            :active="inv.id === layersStore.activeInvestigationId"
            :indent="inv.id !== layersStore.activeInvestigationId"
            @click="layersStore.switchToInvestigation(inv.id)"
          >
            <input
              v-if="editingInvestigation === inv.id"
              v-model="editInvestigationName"
              class="inline-input"
              autofocus
              @click.stop
              @keyup.enter="saveInvestigationEdit"
              @keyup.esc="cancelInvestigationEdit"
              @blur="saveInvestigationEdit"
            />
            <span v-else @dblclick.stop="startEditingInvestigation(inv.id, inv.name)">{{
              inv.name
            }}</span>
            <template #meta>{{ investigationMeta(inv) }}</template>
          </BcRow>
        </template>
      </template>

      <div v-if="creatingNewProject" class="project-row">
        <input
          v-model="newProjectName"
          class="inline-input"
          autofocus
          @keyup.enter="saveNewProject"
          @keyup.esc="cancelProjectCreation"
          @blur="saveNewProject"
        />
      </div>
      <button v-else class="bc-btn new-project" @click="startCreatingProject">+ New project</button>
    </div>

    <ShareDialog
      v-model="showShareDialog"
      :url="shareUrl"
      :name="layersStore.activeInvestigation?.name ?? ''"
    />
    <DeleteDialog
      v-model="showDeleteDialog"
      :type="deleteType"
      :name="deleteTargetName"
      :investigation-count="deleteTargetCount"
      @confirm="executeDelete"
      @cancel="cancelDelete"
    />
  </div>
</template>

<style scoped>
.section {
  padding: 20px var(--bc-pad-x) 16px;
  border-bottom: 1px solid var(--bc-line);
}

.section__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.section__actions {
  display: flex;
  gap: 14px;
  color: var(--bc-grey);
}

.section__title {
  font-size: var(--bc-fs-display);
  font-weight: 300;
  letter-spacing: -0.02em;
  line-height: 1.1;
}

.section__sub {
  margin-top: 4px;
  font-size: var(--bc-fs-body);
  color: var(--bc-grey);
}

.tree {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
}

.project-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: var(--bc-row-y) 0;
  border-top: 1px solid var(--bc-line);
  font-size: var(--bc-fs-body);
}

.project-row__name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.icon-btn {
  background: none;
  border: 0;
  padding: 0;
  color: var(--bc-grey);
  cursor: pointer;
  display: flex;
  align-items: center;
  transition: color var(--bc-t);
}

.icon-btn:hover {
  color: var(--bc-ink);
}

.inline-input {
  flex: 1;
  min-width: 0;
  font: inherit;
  color: inherit;
  background: transparent;
  border: 0;
  outline: none;
  padding: 0;
}

.new-project {
  margin-top: 10px;
  align-self: flex-start;
}
</style>
