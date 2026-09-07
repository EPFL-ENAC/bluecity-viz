import { computed, ref, type Ref } from 'vue'
import { defaultScenarioInputs, defaultTrafficInputs } from './persistence'
import { copyResults, forgetResults } from './trafficResultsCache'
import type { Investigation, Project, ScenarioInputs, TrafficAnalysisInputs } from './types'

export function createInvestigationManagement(
  projects: Ref<Project[]>,
  activeInvestigationId: Ref<string | null>,
  availableResourceSources: Ref<string[]>,
  selectedLayers: Ref<string[]>,
  updateAvailableResourceSources: (sourceIds: string[]) => void,
  updateActiveSources: (sourceIds: string[]) => void,
  updateSelectedLayers: (selection: string[] | null) => void,
  getTrafficAnalysisInputs: () => TrafficAnalysisInputs,
  applyTrafficAnalysisState: (inputs: TrafficAnalysisInputs, investigationId: string) => void,
  getScenarioInputs: () => ScenarioInputs,
  applyScenarioState: (inputs: ScenarioInputs) => void
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

    // Always apply, with empty inputs when the investigation has none, so the
    // previous investigation's scenario and traffic state do not stay on the map.
    applyScenarioState(investigation.scenario ?? defaultScenarioInputs())
    applyTrafficAnalysisState(
      investigation.trafficAnalysis ?? defaultTrafficInputs(),
      investigation.id
    )

    // Clear loading flag
    isLoadingInvestigation.value = false
  } // Save current state as new investigation
  function saveCurrentState(projectId: string) {
    const project = projects.value.find((p) => p.id === projectId)
    if (!project) return

    const trafficState = getTrafficAnalysisInputs()

    const newInvestigation: Investigation = {
      id: `inv-${Date.now()}`,
      name: `Investigation ${project.investigations.length + 1}`,
      selectedSources: [...availableResourceSources.value],
      selectedLayers: [...selectedLayers.value],
      createdAt: new Date(),
      trafficAnalysis: trafficState,
      scenario: getScenarioInputs()
    }

    // Keep the results on screen for the copy we just made.
    copyResults(activeInvestigationId.value, newInvestigation.id)

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

    project.investigations.forEach((inv) => forgetResults(inv.id))

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
        forgetResults(investigationId)

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
    investigation.trafficAnalysis = getTrafficAnalysisInputs()
    investigation.scenario = getScenarioInputs()
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
