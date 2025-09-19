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
      const jsonString = JSON.stringify(shareableState)
      const encoded = btoa(jsonString)
      const url = new URL(window.location.origin + window.location.pathname)
      url.searchParams.set('state', encoded)
      return url.toString()
    } catch (error) {
      if (error instanceof TypeError && error.message.includes('malformed')) {
        console.warn(
          'Failed to generate shareable URL: Invalid character in shareable state for base64 encoding',
          error
        )
      } else {
        console.warn('Failed to generate shareable URL:', error)
      }
      return window.location.origin
    }
  }

  function loadStateFromUrl(): boolean {
    try {
      const urlParams = new URLSearchParams(window.location.search)
      const encodedState = urlParams.get('state')

      if (!encodedState) return false

      // Check for invalid base64 encoding
      let decodedString: string
      try {
        decodedString = atob(encodedState)
      } catch (base64Error) {
        console.warn('Failed to load state from URL: Invalid base64 encoding', base64Error)
        return false
      }

      // Check for malformed JSON
      let decodedState: any
      try {
        decodedState = JSON.parse(decodedString)
      } catch (jsonError) {
        console.warn('Failed to load state from URL: Malformed JSON in decoded state', jsonError)
        return false
      }

      // Check for missing required properties
      if (!decodedState.name) {
        console.warn(
          'Failed to load state from URL: Missing required property "name" in decoded state'
        )
        return false
      }

      // Validate property types
      if (decodedState.selectedSources && !Array.isArray(decodedState.selectedSources)) {
        console.warn('Failed to load state from URL: Property "selectedSources" must be an array')
        return false
      }

      if (decodedState.selectedLayers && !Array.isArray(decodedState.selectedLayers)) {
        console.warn('Failed to load state from URL: Property "selectedLayers" must be an array')
        return false
      }

      if (decodedState.sp0Period && typeof decodedState.sp0Period !== 'string') {
        console.warn('Failed to load state from URL: Property "sp0Period" must be a string')
        return false
      }

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
      console.warn('Failed to load state from URL: Unexpected error during state loading', error)
      return false
    }
  }

  return {
    generateShareableUrl,
    loadStateFromUrl
  }
}
