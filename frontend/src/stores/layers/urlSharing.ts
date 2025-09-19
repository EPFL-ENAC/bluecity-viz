import type { Ref } from 'vue'
import type { Investigation } from './types'

export function createUrlSharingComposable(
  activeInvestigation: Ref<Investigation | null>,
  sp0Period: Ref<string>,
  projects: Ref<any[]>,
  switchToInvestigation: (id: string) => void
) {
  function generateShareableUrl(): string {
    const currentInvestigation = activeInvestigation.value
    if (!currentInvestigation) return window.location.origin

    const shareableState = {
      name: currentInvestigation.name,
      selectedSources: currentInvestigation.selectedSources,
      selectedLayers: currentInvestigation.selectedLayers,
      sp0Period: sp0Period.value
    }

    try {
      const encoded = btoa(JSON.stringify(shareableState))
      const url = new URL(window.location.origin + window.location.pathname)
      url.searchParams.set('state', encoded)
      return url.toString()
    } catch (error) {
      console.warn('Failed to generate shareable URL:', error)
      return window.location.origin
    }
  }

  function loadStateFromUrl(): boolean {
    try {
      const urlParams = new URLSearchParams(window.location.search)
      const encodedState = urlParams.get('state')

      if (!encodedState) return false

      const decodedState = JSON.parse(atob(encodedState))

      // Create a temporary investigation with the shared state
      const sharedInvestigation: Investigation = {
        id: `shared-${Date.now()}`,
        name: decodedState.name + ' (Shared)',
        selectedSources: decodedState.selectedSources || [],
        selectedLayers: decodedState.selectedLayers || [],
        createdAt: new Date()
      }

      // Add to first project or create a new one
      if (projects.value.length === 0) {
        projects.value.push({
          id: 'shared-project',
          name: 'Shared Investigations',
          expanded: true,
          investigations: []
        })
      }

      projects.value[0].investigations.unshift(sharedInvestigation)

      // Switch to the shared investigation
      switchToInvestigation(sharedInvestigation.id)

      // Update the period if provided
      if (decodedState.sp0Period) {
        sp0Period.value = decodedState.sp0Period
      }

      // Clear the URL parameter to keep URL clean
      const url = new URL(window.location.href)
      url.searchParams.delete('state')
      window.history.replaceState({}, '', url.toString())

      return true
    } catch (error) {
      console.warn('Failed to load state from URL:', error)
      return false
    }
  }

  return {
    generateShareableUrl,
    loadStateFromUrl
  }
}
