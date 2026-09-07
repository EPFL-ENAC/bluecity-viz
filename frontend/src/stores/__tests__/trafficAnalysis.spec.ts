import { fetchBaseline, fetchGraphInfo } from '@/services/trafficAnalysis'
import {
  EXPECTED_PUBLIC_KEYS,
  EXPECTED_SCALES,
  EXPECTED_STATE_KEYS,
  makeUsage
} from '@/stores/__tests__/fixtures/trafficScales'
import { useScenarioStore } from '@/stores/scenario'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

// vi.mock is hoisted above the imports, so the factory cannot use anything
// declared here. importActual keeps the rest of the module real.
vi.mock('@/services/trafficAnalysis', async () => ({
  ...(await vi.importActual<typeof import('@/services/trafficAnalysis')>(
    '@/services/trafficAnalysis'
  )),
  fetchBaseline: vi.fn(),
  fetchGraphInfo: vi.fn()
}))

function baselineRows(count: number) {
  return Array.from({ length: count }, (_, i) => ({
    u: i,
    v: i + 1,
    count: i,
    frequency: i / count
  }))
}

type Mode = (typeof EXPECTED_SCALES.modes)[number]

describe('traffic analysis store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(fetchBaseline).mockReset()
    vi.mocked(fetchGraphInfo).mockReset()
  })

  it('offers the same modes and picks delta when the routes moved', () => {
    const store = useTrafficAnalysisStore()
    const usage = makeUsage()
    store.setEdgeUsage(usage, usage)

    expect(store.availableVisualizations.map((m) => m.value)).toEqual([...EXPECTED_SCALES.modes])
    expect(store.activeVisualization).toBe(EXPECTED_SCALES.autoSelected)
    expect(store.hasCalculatedRoutes).toBe(true)
  })

  it('gives the same scale and the same colors as before the refactor', () => {
    const store = useTrafficAnalysisStore()
    const usage = makeUsage()
    store.setEdgeUsage(usage, usage)

    for (const mode of EXPECTED_SCALES.modes) {
      store.setActiveVisualization(mode)
      const want = EXPECTED_SCALES.perMode[mode as Mode]

      expect(store.legendMode, mode).toBe(want.legendMode)
      expect(store.minValue, mode).toBeCloseTo(want.min, 10)
      expect(store.maxValue, mode).toBeCloseTo(want.max, 10)

      const mid = (store.minValue + store.maxValue) / 2
      const got = [
        store.getColor(store.minValue),
        store.getColor(mid),
        store.getColor(store.maxValue),
        store.getColor(0)
      ]
      expect(got, mode).toEqual(want.colors.map((c) => [...c]))
    }
  })

  it('falls back to grey with no scale', () => {
    const store = useTrafficAnalysisStore()
    expect(store.getColor(42)).toEqual([136, 136, 136])

    const usage = makeUsage()
    store.setEdgeUsage(usage, usage)
    store.setActiveVisualization('none')
    expect(store.legendMode).toBe('none')
    expect(store.colorScale).toBeNull()
    expect(store.getColor(42)).toEqual([136, 136, 136])
  })

  it('clears every scale with the results', () => {
    const store = useTrafficAnalysisStore()
    const usage = makeUsage()
    store.setEdgeUsage(usage, usage)
    store.clearResults()

    expect(store.newEdgeUsage).toEqual([])
    expect(store.originalEdgeUsage).toEqual([])
    expect(store.impactStatistics).toBeNull()
    expect(store.activeVisualization).toBe('none')
    expect(store.legendMode).toBe('none')
    expect(store.colorScale).toBeNull()
    expect(store.minValue).toBe(0)
    expect(store.maxValue).toBe(0)
    expect(store.filterBusRoutes).toBe(false)

    // and a mode that had a scale before must not bring it back
    store.setActiveVisualization('delta')
    expect(store.colorScale).toBeNull()
    expect(store.legendMode).toBe('none')
  })

  it('keeps the names its consumers use', () => {
    const store = useTrafficAnalysisStore()
    const publicKeys = Object.keys(store)
      .filter((k) => !k.startsWith('$') && !k.startsWith('_'))
      .sort()

    expect(publicKeys).toEqual([...EXPECTED_PUBLIC_KEYS].sort())
    expect(Object.keys(store.$state).sort()).toEqual([...EXPECTED_STATE_KEYS].sort())
  })

  it('is stale when the scenario moved after the run', () => {
    const store = useTrafficAnalysisStore()
    const scenario = useScenarioStore()

    // nothing computed yet, so nothing to be stale about
    expect(store.isStale).toBe(false)

    store.setEdgeUsage([{ u: 1, v: 2, count: 1, frequency: 1 }], [], undefined, null, scenario.hash)
    expect(store.isStale).toBe(false)

    scenario.set('1-2', { action: 'remove', dir: 'both', name: 'Rue de Test' })
    expect(store.isStale).toBe(true)
  })
  it('restores without the bulk arrays', () => {
    const store = useTrafficAnalysisStore()
    // a saved investigation that no longer keeps the results
    expect(() =>
      store.restoreState({
        isOpen: true,
        activeVisualization: 'none'
      })
    ).not.toThrow()

    expect(store.isOpen).toBe(true)
    expect(store.nodePairs).toEqual([])
    expect(store.originalEdgeUsage).toEqual([])
    expect(store.newEdgeUsage).toEqual([])
    expect(store.impactStatistics).toBeNull()
    expect(store.isRestoring).toBe(false)
  })

  it('restores the routing options when the state has them', () => {
    const store = useTrafficAnalysisStore()
    store.restoreState({
      isOpen: true,
      nodePairs: [],
      originalEdgeUsage: [],
      newEdgeUsage: [],
      impactStatistics: null,
      activeVisualization: 'none',
      useCongestionModel: true,
      congestionIterations: 4,
      elasticDemand: true,
      filterBusRoutes: true
    })

    expect(store.useCongestionModel).toBe(true)
    expect(store.congestionIterations).toBe(4)
    expect(store.elasticDemand).toBe(true)
    expect(store.filterBusRoutes).toBe(true)
  })

  it('leaves the routing options alone when the state omits them', () => {
    const store = useTrafficAnalysisStore()
    store.useCongestionModel = true
    store.congestionIterations = 3

    store.restoreState({ isOpen: false, activeVisualization: 'none' })

    expect(store.useCongestionModel).toBe(true)
    expect(store.congestionIterations).toBe(3)
  })

  it('drops the results when the pair count changes, keeps them when it does not', () => {
    const store = useTrafficAnalysisStore()
    const usage = makeUsage()
    store.setEdgeUsage(usage, usage, undefined, 20000)

    expect(store.resultOdPairs).toBe(20000)

    // same count, nothing happens
    store.setOdPairs(null)
    expect(store.hasCalculatedRoutes).toBe(true)

    store.setOdPairs(76200)
    expect(store.odPairs).toBe(76200)
    expect(store.hasCalculatedRoutes).toBe(false)
    expect(store.newEdgeUsage).toEqual([])
    expect(store.resultOdPairs).toBeNull()
    expect(store.activeVisualization).toBe('none')
  })

  it('fetches one baseline per count and keeps it', async () => {
    const store = useTrafficAnalysisStore()
    vi.mocked(fetchBaseline).mockImplementation(async (odPairs?: number) => ({
      total_routes: odPairs ?? 20000,
      od_pairs: odPairs ?? 20000,
      edge_usage: baselineRows(3)
    }))

    const first = await store.getBaseline(20000)
    expect(first.odPairs).toBe(20000)
    expect(first.rows).toHaveLength(3)

    await store.getBaseline(20000)
    expect(fetchBaseline).toHaveBeenCalledTimes(1)

    await store.getBaseline(76200)
    expect(fetchBaseline).toHaveBeenCalledTimes(2)
    expect(vi.mocked(fetchBaseline).mock.calls[1][0]).toBe(76200)

    // the first one is still cached
    await store.getBaseline(20000)
    expect(fetchBaseline).toHaveBeenCalledTimes(2)
  })

  it('asks once when two calls overlap, and retries after a failure', async () => {
    const store = useTrafficAnalysisStore()
    vi.mocked(fetchBaseline).mockResolvedValue({
      total_routes: 20000,
      od_pairs: 20000,
      edge_usage: baselineRows(2)
    })

    await Promise.all([store.getBaseline(20000), store.getBaseline(20000)])
    expect(fetchBaseline).toHaveBeenCalledTimes(1)

    vi.mocked(fetchBaseline).mockReset()
    vi.mocked(fetchBaseline).mockRejectedValueOnce(new Error('server down'))
    await expect(store.getBaseline(76200)).rejects.toThrow('server down')

    vi.mocked(fetchBaseline).mockResolvedValue({
      total_routes: 76200,
      od_pairs: 76200,
      edge_usage: baselineRows(2)
    })
    const retry = await store.getBaseline(76200)
    expect(retry.odPairs).toBe(76200)
    expect(fetchBaseline).toHaveBeenCalledTimes(2)
  })

  it('reads the pair counts from the server once', async () => {
    const store = useTrafficAnalysisStore()
    vi.mocked(fetchGraphInfo).mockResolvedValue({
      node_count: 1,
      edge_count: 2,
      od_pairs: 76200,
      od_pairs_default: 20000,
      od_pairs_max: 76400
    })

    await store.loadGraphInfo()
    await store.loadGraphInfo()

    expect(fetchGraphInfo).toHaveBeenCalledTimes(1)
    expect(store.odPairsDefault).toBe(20000)
    expect(store.odPairsMax).toBe(76400)
    // the full choice sends what was really sampled, the server clamps anyway
    expect(store.odPairsFull).toBe(76200)
  })

  it('restores the pair count without dropping the restored results', () => {
    const store = useTrafficAnalysisStore()
    const usage = makeUsage()

    store.restoreState({
      isOpen: true,
      edgeModifications: [],
      originalEdgeUsage: usage,
      newEdgeUsage: usage,
      activeVisualization: 'frequency',
      odPairs: 76200,
      resultOdPairs: 76200
    })

    expect(store.odPairs).toBe(76200)
    expect(store.resultOdPairs).toBe(76200)
    expect(store.hasCalculatedRoutes).toBe(true)
  })

  it('restores the chosen count with no results', () => {
    const store = useTrafficAnalysisStore()
    store.restoreState({
      isOpen: true,
      activeVisualization: 'none',
      odPairs: 76200
    })

    expect(store.odPairs).toBe(76200)
    expect(store.resultOdPairs).toBeNull()
    expect(store.hasCalculatedRoutes).toBe(false)
  })

  it('keeps the saved mode when it restores results', () => {
    const store = useTrafficAnalysisStore()
    const usage = makeUsage()

    store.restoreState({
      isOpen: true,
      nodePairs: [],
      originalEdgeUsage: usage,
      newEdgeUsage: usage,
      impactStatistics: null,
      activeVisualization: 'co2'
    })

    // setEdgeUsage would have picked delta, the saved mode wins
    expect(store.activeVisualization).toBe('co2')
    expect(store.legendMode).toBe('co2')
    expect(store.minValue).toBeCloseTo(EXPECTED_SCALES.perMode.co2.min, 10)
  })
})
