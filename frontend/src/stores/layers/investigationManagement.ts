import { computed, ref, type Ref } from 'vue'
import type { Investigation, Project } from './types'

export function createInvestigationManagement(
  projects: Ref<Project[]>,
  activeInvestigationId: Ref<string | null>,
  availableResourceSources: Ref<string[]>,
  selectedLayers: Ref<string[]>,
  updateAvailableResourceSources: (sourceIds: string[]) => void,
  updateActiveSources: (sourceIds: string[]) => void,
  updateSelectedLayers: (selection: string[] | null) => void
) {
  // Track if we're currently loading an investigation to prevent auto-updates
  const isLoadingInvestigation = ref(false)

  // Computed active investigation
  const activeInvestigation = computed(() => {
    for (const project of projects.value) {
      const investigation = project.investigations.find(
        (inv) => inv.id === activeInvestigationId.value
      )
      if (investigation) return investigation
    }
    return null
  })

  // Toggle project expansion
  function toggleProject(projectId: string) {
    const project = projects.value.find((p) => p.id === projectId)
    if (project) {
      project.expanded = !project.expanded
    }
  }

  // Find investigation by ID
  function findInvestigation(id: string): Investigation | null {
    for (const project of projects.value) {
      const investigation = project.investigations.find((inv) => inv.id === id)
      if (investigation) return investigation
    }
    return null
  }

  // Switch to investigation
  function switchToInvestigation(investigationId: string | null) {
    if (!investigationId) return

    const investigation = findInvestigation(investigationId)
    if (!investigation) return

    // Set loading flag to prevent auto-updates during state restoration
    isLoadingInvestigation.value = true
    activeInvestigationId.value = investigationId

    // Apply investigation state to the store
    updateAvailableResourceSources(investigation.selectedSources)
    updateActiveSources(investigation.selectedSources)
    updateSelectedLayers(investigation.selectedLayers)

    // Clear loading flag
    isLoadingInvestigation.value = false
  }

  // Save current state as new investigation
  function saveCurrentState(projectId: string) {
    const project = projects.value.find((p) => p.id === projectId)
    if (!project) return

    const newInvestigation: Investigation = {
      id: `inv-${Date.now()}`,
      name: `Investigation ${project.investigations.length + 1}`,
      selectedSources: [...availableResourceSources.value],
      selectedLayers: [...selectedLayers.value],
      createdAt: new Date()
    }

    project.investigations.push(newInvestigation)
    activeInvestigationId.value = newInvestigation.id
  }

  // Remove investigation
  function removeInvestigation(investigationId: string) {
    for (const project of projects.value) {
      const index = project.investigations.findIndex((inv) => inv.id === investigationId)
      if (index !== -1) {
        project.investigations.splice(index, 1)

        // If removing active investigation, switch to first available
        if (activeInvestigationId.value === investigationId) {
          const firstInvestigation = projects.value.flatMap((p) => p.investigations)[0]
          if (firstInvestigation) {
            switchToInvestigation(firstInvestigation.id)
          } else {
            activeInvestigationId.value = null
          }
        }
        break
      }
    }
  }

  // Update current investigation with current state
  function updateCurrentInvestigation() {
    // Don't update if we're currently loading an investigation
    if (isLoadingInvestigation.value) return
    if (!activeInvestigationId.value) return

    const investigation = findInvestigation(activeInvestigationId.value)
    if (!investigation) return

    // Update the investigation with current state
    investigation.selectedSources = [...availableResourceSources.value]
    investigation.selectedLayers = [...selectedLayers.value]
  }

  return {
    isLoadingInvestigation,
    activeInvestigation,
    toggleProject,
    findInvestigation,
    switchToInvestigation,
    saveCurrentState,
    removeInvestigation,
    updateCurrentInvestigation
  }
}
