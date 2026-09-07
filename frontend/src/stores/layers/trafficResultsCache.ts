import { markRaw } from 'vue'
import type { TrafficResults } from './types'

// Results of a traffic run, kept in memory per investigation. They never go
// into the `projects` ref (too big to clone and to persist), so switching
// investigations in the same session keeps them, and a reload drops them.
const cache = new Map<string, TrafficResults>()

export function rememberResults(investigationId: string | null, results: TrafficResults) {
  if (!investigationId) return

  if (results.newEdgeUsage.length === 0 && results.originalEdgeUsage.length === 0) {
    cache.delete(investigationId)
    return
  }

  // markRaw: the arrays are big, we never want Vue to walk them.
  cache.set(investigationId, markRaw({ ...results }))
}

export function getResults(investigationId: string | null): TrafficResults | null {
  if (!investigationId) return null
  return cache.get(investigationId) ?? null
}

export function forgetResults(investigationId: string) {
  cache.delete(investigationId)
}

export function copyResults(fromId: string | null, toId: string) {
  const results = getResults(fromId)
  if (results) cache.set(toId, results)
}

// Used by the tests to start from a clean cache.
export function clearResultsCache() {
  cache.clear()
}
