import { computed, ref, type Ref } from 'vue'
import type { Investigation, Project, TrafficAnalysisState } from './types'

export function createInvestigationManagement(
  projects: Ref<Project[]>,
  activeInvestigationId: Ref<string | null>,
  availableResourceSources: Ref<string[]>,
  selectedLayers: Ref<string[]>,
  updateAvailableResourceSources: (sourceIds: string[]) => void,
  updateActiveSources: (sourceIds: string[]) => void,
  updateSelectedLayers: (selection: string[] | null) => void,
  getTrafficAnalysisState: () => TrafficAnalysisState,
  applyTrafficAnalysisState: (state: TrafficAnalysisState) => void
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

    // Apply traffic analysis state if it exists
    if (investigation.trafficAnalysis) {
      applyTrafficAnalysisState(investigation.trafficAnalysis)
    }

    // Clear loading flag
    isLoadingInvestigation.value = false
  } // Save current state as new investigation
  function saveCurrentState(projectId: string) {
    const project = projects.value.find((p) => p.id === projectId)
    if (!project) return

    const trafficState = getTrafficAnalysisState()

    const newInvestigation: Investigation = {
      id: `inv-${Date.now()}`,
      name: `Investigation ${project.investigations.length + 1}`,
      selectedSources: [...availableResourceSources.value],
      selectedLayers: [...selectedLayers.value],
      createdAt: new Date(),
      trafficAnalysis: trafficState
    }

    project.investigations.push(newInvestigation)
    activeInvestigationId.value = newInvestigation.id
  }

  // Create new project
  function createProject(name: string) {
    const newProject: Project = {
      id: `project-${Date.now()}`,
      name,
      expanded: true,
      investigations: []
    }

    projects.value.push(newProject)
  }

  // Remove project
  function removeProject(projectId: string) {
    const index = projects.value.findIndex((p) => p.id === projectId)
    if (index === -1) return

    const project = projects.value[index]

    // Check if any investigation in this project is active
    const hasActiveInvestigation = project.investigations.some(
      (inv) => inv.id === activeInvestigationId.value
    )

    // Remove the project
    projects.value.splice(index, 1)

    // If we removed the project with the active investigation, switch to first available
    if (hasActiveInvestigation) {
      const firstInvestigation = projects.value.flatMap((p) => p.investigations)[0]
      if (firstInvestigation) {
        switchToInvestigation(firstInvestigation.id)
      } else {
        activeInvestigationId.value = null
      }
    }
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
    investigation.trafficAnalysis = getTrafficAnalysisState()
  }

  return {
    isLoadingInvestigation,
    activeInvestigation,
    toggleProject,
    findInvestigation,
    switchToInvestigation,
    saveCurrentState,
    createProject,
    removeProject,
    removeInvestigation,
    updateCurrentInvestigation
  }
}
