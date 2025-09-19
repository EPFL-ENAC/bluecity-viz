import type { Investigation, PersistedState, Project } from './types'

const STORAGE_KEY = 'bluecity-layers-store'

export function loadPersistedState(): Partial<PersistedState> {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      const parsed = JSON.parse(stored)
      // Convert date strings back to Date objects for investigations
      if (parsed.projects) {
        parsed.projects.forEach((project: Project) => {
          project.investigations.forEach((investigation: Investigation) => {
            investigation.createdAt = new Date(investigation.createdAt)
          })
        })
      }
      return parsed
    }
  } catch (error) {
    console.warn('Failed to load persisted state:', error)
  }
  return {}
}

export function saveStateToStorage(state: PersistedState) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch (error) {
    console.warn('Failed to save state to storage:', error)
  }
}

export function clearPersistedData() {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch (error) {
    console.warn('Failed to clear persisted data:', error)
  }
}
