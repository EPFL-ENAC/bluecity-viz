import { useCVRPStore } from '@/stores/cvrp'
import { useScenarioStore } from '@/stores/scenario'
import { STORYLINE_STORAGE_KEY, useStorylineStore } from '@/stores/storyline'
import { useTrafficAnalysisStore, type EdgeUsageStats } from '@/stores/trafficAnalysis'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'

// jsdom does not expose localStorage as a global here, so we give the store a
// small in-memory one, the same way as theme.spec.ts.
function makeStorage(initial: Record<string, string> = {}) {
  const data = new Map(Object.entries(initial))
  return {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => void data.set(key, value),
    removeItem: (key: string) => void data.delete(key),
    clear: () => data.clear()
  }
}

/** One row is enough, hasCalculatedRoutes only looks at the length. */
const ROWS: EdgeUsageStats[] = [{ u: 1, v: 2, count: 3, frequency: 3 }]

describe('storyline store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.stubGlobal('localStorage', makeStorage())
  })

  it('starts both tools on the initial model', () => {
    const store = useStorylineStore()
    expect(store.phases).toEqual({ routing: 'init', cvrp: 'init' })
    expect(store.current).toBe('init')
  })

  it('validates one tool only', () => {
    const store = useStorylineStore()
    store.validate('routing')
    expect(store.phaseOf('routing')).toBe('simulation')
    expect(store.phaseOf('cvrp')).toBe('init')
    expect(store.current).toBe('simulation')

    useScenarioStore().activeTab = 'cvrp'
    expect(store.current).toBe('init')
  })

  it('keeps the phase across a reload', async () => {
    const storage = makeStorage()
    vi.stubGlobal('localStorage', storage)
    useStorylineStore().validate('cvrp')
    await nextTick()
    expect(JSON.parse(storage.getItem(STORYLINE_STORAGE_KEY) ?? '{}')).toEqual({
      routing: 'init',
      cvrp: 'simulation'
    })

    // a new pinia reads the same storage, like a page reload
    setActivePinia(createPinia())
    expect(useStorylineStore().phases).toEqual({ routing: 'init', cvrp: 'simulation' })
  })

  it('falls back to the initial model for a value it does not know', () => {
    vi.stubGlobal(
      'localStorage',
      makeStorage({ [STORYLINE_STORAGE_KEY]: '{"routing":"running","cvrp":42}' })
    )
    expect(useStorylineStore().phases).toEqual({ routing: 'init', cvrp: 'init' })

    setActivePinia(createPinia())
    vi.stubGlobal('localStorage', makeStorage({ [STORYLINE_STORAGE_KEY]: 'not json' }))
    expect(useStorylineStore().phases).toEqual({ routing: 'init', cvrp: 'init' })
  })

  it('drops the routing result on return, and keeps the edges', async () => {
    const store = useStorylineStore()
    const traffic = useTrafficAnalysisStore()
    const scenario = useScenarioStore()
    scenario.set('3-7', { action: 'remove', dir: 'both', name: 'Avenue de Cour' })
    store.validate('cvrp')
    traffic.setEdgeUsage(ROWS, ROWS)
    await nextTick()
    expect(store.phaseOf('routing')).toBe('simulation')

    store.returnToInit('routing')
    await nextTick()
    expect(store.phaseOf('routing')).toBe('init')
    expect(traffic.hasCalculatedRoutes).toBe(false)
    expect(scenario.count).toBe(1)
    expect(store.phaseOf('cvrp')).toBe('simulation')
  })

  it('drops the CVRP result on return, and keeps the edges', async () => {
    const store = useStorylineStore()
    const cvrp = useCVRPStore()
    const scenario = useScenarioStore()
    scenario.set('3-7', { action: '30', dir: 'fwd', name: 'Avenue de Cour' })
    store.validate('routing')
    // hasResult only asks whether there is a result object
    cvrp.lastResult = { n_routes: 2 } as never
    await nextTick()
    expect(store.phaseOf('cvrp')).toBe('simulation')

    store.returnToInit('cvrp')
    await nextTick()
    expect(store.phaseOf('cvrp')).toBe('init')
    expect(cvrp.hasResult).toBe(false)
    expect(scenario.count).toBe(1)
    expect(store.phaseOf('routing')).toBe('simulation')
  })

  it('moves to simulation when a result lands in the initial model', async () => {
    const store = useStorylineStore()
    expect(store.phaseOf('routing')).toBe('init')
    // an investigation restored with its result, for example
    useTrafficAnalysisStore().originalEdgeUsage = ROWS
    await nextTick()
    expect(store.phaseOf('routing')).toBe('simulation')
    expect(store.phaseOf('cvrp')).toBe('init')
  })

  it('reads a result that is already there when it starts', () => {
    useTrafficAnalysisStore().originalEdgeUsage = ROWS
    expect(useStorylineStore().phaseOf('routing')).toBe('simulation')
  })
})
