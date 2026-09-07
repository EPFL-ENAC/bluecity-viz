import { useLayersStore } from '@/stores/layers'
import { useScenarioStore } from '@/stores/scenario'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { migratePersistedState, SCHEMA_VERSION } from '../layers/persistence'
import { clearResultsCache } from '../layers/trafficResultsCache'

const STORAGE_KEY = 'bluecity-layers-store'

// Same trick as theme.spec.ts: jsdom does not give us localStorage here, so we
// use a small in-memory one and can seed it before the store reads it.
function makeStorage(initial: Record<string, string> = {}) {
  const data = new Map(Object.entries(initial))
  return {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => void data.set(key, value),
    removeItem: (key: string) => void data.delete(key),
    clear: () => data.clear()
  }
}

function edgeRows(count: number) {
  return Array.from({ length: count }, (_, i) => ({
    u: i,
    v: i + 1,
    count: i,
    frequency: i / count
  }))
}

// The v1 shape: the whole result of a run inside the investigation.
function oldStoredState() {
  return JSON.stringify({
    selectedLayers: ['lausanne_pop_density-layer'],
    availableResourceSources: ['lausanne_migration'],
    activeSources: ['lausanne_migration'],
    activeInvestigationId: 'inv-1',
    sp0Period: '2020-2023',
    expandedGroups: {},
    trafficPanelOpen: true,
    projects: [
      {
        id: 'project-1',
        name: 'Project 1',
        expanded: true,
        investigations: [
          {
            id: 'inv-1',
            name: 'Investigation 1',
            selectedSources: ['lausanne_migration'],
            selectedLayers: ['lausanne_pop_density-layer'],
            createdAt: '2024-01-01T00:00:00.000Z',
            trafficAnalysis: {
              isOpen: true,
              edgeModifications: [{ u: 1, v: 2, action: 'remove', name: 'Rue X' }],
              nodePairs: [{ origin: 1, destination: 2 }],
              originalEdgeUsage: edgeRows(50),
              newEdgeUsage: edgeRows(50),
              impactStatistics: { total_distance_km: 12 },
              activeVisualization: 'frequency'
            }
          }
        ]
      }
    ]
  })
}

const BULK_KEYS = ['nodePairs', 'originalEdgeUsage', 'newEdgeUsage', 'impactStatistics']

describe('layers store persistence', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    clearResultsCache()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('drops the bulk fields when migrating an old entry', () => {
    vi.stubGlobal('localStorage', makeStorage({ [STORAGE_KEY]: oldStoredState() }))

    const store = useLayersStore()
    const investigation = store.findInvestigation('inv-1')

    expect(investigation).not.toBeNull()
    const traffic = investigation!.trafficAnalysis as unknown as Record<string, unknown>
    expect(traffic.isOpen).toBe(true)
    expect(traffic.activeVisualization).toBe('frequency')
    // v4 moved the modifications out of the tool into the shared scenario
    expect(traffic).not.toHaveProperty('edgeModifications')
    expect(investigation!.scenario?.edgeModifications).toEqual([
      { key: '1-2', action: 'remove', dir: 'fwd', name: 'Rue X' }
    ])
    // v1 knew nothing about the pair count, it reads back as the server default
    expect(traffic.odPairs).toBeNull()
    for (const key of BULK_KEYS) {
      expect(traffic).not.toHaveProperty(key)
    }
  })

  it('keeps a saved pair count and drops a broken one', () => {
    const withCount = (odPairs: unknown) =>
      migratePersistedState({
        projects: [
          {
            id: 'project-1',
            investigations: [
              {
                id: 'inv-1',
                name: 'Investigation 1',
                trafficAnalysis: { isOpen: true, odPairs }
              }
            ]
          }
        ]
      }).projects?.[0].investigations[0].trafficAnalysis

    expect(withCount(76200)?.odPairs).toBe(76200)
    expect(withCount(0)?.odPairs).toBeNull()
    expect(withCount('76200')?.odPairs).toBeNull()
    expect(withCount(undefined)?.odPairs).toBeNull()
  })

  it('does not crash on a broken or empty entry', () => {
    expect(migratePersistedState(null)).toEqual({})
    expect(migratePersistedState('nope')).toEqual({})
    expect(migratePersistedState({})).toEqual({ version: SCHEMA_VERSION })
    expect(migratePersistedState({ projects: null })).not.toHaveProperty('projects')
    expect(migratePersistedState({ projects: [{ investigations: null }] }).projects).toHaveLength(1)
  })

  it('never writes the results to storage', async () => {
    const storage = makeStorage()
    vi.stubGlobal('localStorage', storage)

    const store = useLayersStore()
    const traffic = useTrafficAnalysisStore()

    traffic.setEdgeUsage(edgeRows(200), edgeRows(200), undefined)
    store.updateSelectedLayers(['lausanne_pop_density-layer'])
    await nextTick()
    store.persistState()

    const stored = storage.getItem(STORAGE_KEY) as string
    expect(stored).not.toContain('newEdgeUsage')
    expect(stored).not.toContain('originalEdgeUsage')
    expect(JSON.parse(stored).version).toBe(SCHEMA_VERSION)
  })

  it('writes once for a burst of updates', async () => {
    vi.useFakeTimers()
    const storage = makeStorage()
    const setItem = vi.spyOn(storage, 'setItem')
    vi.stubGlobal('localStorage', storage)

    const store = useLayersStore()
    await nextTick()
    setItem.mockClear()

    for (let i = 0; i < 10; i++) {
      store.updateSelectedLayers([`layer-${i}`])
      await nextTick()
    }

    expect(setItem).not.toHaveBeenCalled()
    vi.runAllTimers()
    expect(setItem).toHaveBeenCalledTimes(1)
  })

  it('clears the traffic state when the next investigation has none', async () => {
    vi.stubGlobal('localStorage', makeStorage())

    const store = useLayersStore()
    const traffic = useTrafficAnalysisStore()
    const scenario = useScenarioStore()

    store.switchToInvestigation('inv-1')
    traffic.openPanel()
    scenario.set('1-2', { action: 'remove', dir: 'both', name: 'Rue X' })
    traffic.setEdgeUsage(edgeRows(20), edgeRows(20), { total_distance_km: 12 } as any)
    traffic.setActiveVisualization('frequency')
    await nextTick()

    // inv-2 has no saved analysis, so this is the case we care about.
    expect(store.findInvestigation('inv-2')?.trafficAnalysis).toBeUndefined()

    store.switchToInvestigation('inv-2')

    expect(scenario.count).toBe(0)
    expect(traffic.newEdgeUsage).toHaveLength(0)
    expect(traffic.originalEdgeUsage).toHaveLength(0)
    expect(traffic.impactStatistics).toBeNull()
    expect(traffic.activeVisualization).toBe('none')
  })

  it('gives the results back when coming back in the same session', async () => {
    vi.stubGlobal('localStorage', makeStorage())

    const store = useLayersStore()
    const traffic = useTrafficAnalysisStore()
    const scenario = useScenarioStore()

    store.switchToInvestigation('inv-1')
    traffic.openPanel()
    scenario.set('1-2', { action: 'remove', dir: 'both', name: 'Rue X' })
    traffic.setEdgeUsage(edgeRows(20), edgeRows(20), { total_distance_km: 12 } as any)
    traffic.setActiveVisualization('frequency')
    await nextTick()

    store.switchToInvestigation('inv-2')
    await nextTick()
    store.switchToInvestigation('inv-1')

    expect(scenario.get('1-2')).toEqual({ action: 'remove', dir: 'both', name: 'Rue X' })
    expect(traffic.newEdgeUsage).toHaveLength(20)
    expect(traffic.activeVisualization).toBe('frequency')
  })

  it('keeps the inputs across a reload', async () => {
    const storage = makeStorage()
    vi.stubGlobal('localStorage', storage)

    const store = useLayersStore()
    const traffic = useTrafficAnalysisStore()
    const scenario = useScenarioStore()

    traffic.openPanel()
    scenario.set('1-2', { action: 'remove', dir: 'both', name: 'Rue X' })
    traffic.setActiveVisualization('frequency')
    traffic.useCongestionModel = true
    traffic.congestionIterations = 3
    traffic.setOdPairs(76200)
    store.updateSelectedLayers(['lausanne_pop_density-layer'])
    await nextTick()
    store.persistState()

    // Reload: new pinia, new stores, same storage. The in-memory results are
    // gone on purpose, the inputs come back.
    setActivePinia(createPinia())
    clearResultsCache()

    const reloaded = useLayersStore()
    reloaded.initializeInvestigations()
    const reloadedTraffic = useTrafficAnalysisStore()

    expect(reloaded.selectedLayers).toEqual(['lausanne_pop_density-layer'])
    expect(reloadedTraffic.isOpen).toBe(true)
    expect(useScenarioStore().get('1-2')).toEqual({
      action: 'remove',
      dir: 'both',
      name: 'Rue X'
    })
    expect(reloadedTraffic.activeVisualization).toBe('frequency')
    expect(reloadedTraffic.useCongestionModel).toBe(true)
    expect(reloadedTraffic.congestionIterations).toBe(3)
    // the count comes back, the results do not, the user clicks Calculate again
    expect(reloadedTraffic.odPairs).toBe(76200)
    expect(reloadedTraffic.resultOdPairs).toBeNull()
    expect(reloadedTraffic.newEdgeUsage).toHaveLength(0)
  })

  it('gives the count back with the results in the same session', async () => {
    vi.stubGlobal('localStorage', makeStorage())

    const store = useLayersStore()
    const traffic = useTrafficAnalysisStore()

    store.switchToInvestigation('inv-1')
    traffic.setOdPairs(76200)
    traffic.setEdgeUsage(edgeRows(20), edgeRows(20), undefined, 76200)
    await nextTick()

    store.switchToInvestigation('inv-2')
    await nextTick()
    store.switchToInvestigation('inv-1')

    expect(traffic.odPairs).toBe(76200)
    expect(traffic.resultOdPairs).toBe(76200)
    expect(traffic.newEdgeUsage).toHaveLength(20)
  })
})
