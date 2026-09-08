import {
  ApiError,
  createArea,
  fetchArea,
  fetchBaseline,
  fetchGraphInfo
} from '@/services/trafficAnalysis'
import {
  EXPECTED_PUBLIC_KEYS,
  EXPECTED_SCALES,
  EXPECTED_STATE_KEYS,
  makeUsage
} from '@/stores/__tests__/fixtures/trafficScales'
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
  fetchGraphInfo: vi.fn(),
  fetchArea: vi.fn(),
  createArea: vi.fn(),
  fetchAreaLimits: vi.fn().mockRejectedValue(new Error('not in this test'))
}))

const BERN = { kind: 'circle' as const, lon: 7.44, lat: 46.95, radiusM: 3000 }
const BERN_ID = 'c_7.4400_46.9500_3000'

function areaInfo(id: string) {
  return {
    id,
    kind: 'circle',
    name: id,
    circle: null,
    polygon: null,
    bbox: null,
    node_count: 5000,
    edge_count: 9000,
    scc_fraction: 1,
    od_pairs: 40000,
    od_pairs_default: 20000,
    od_pairs_max: 40000,
    status: 'ready',
    build_ms: 100,
    cached: false
  }
}

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
    vi.mocked(fetchArea).mockReset()
    vi.mocked(createArea).mockReset()
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

  it('cycles a modification remove then 50 then 30 then 10 then off', () => {
    const store = useTrafficAnalysisStore()
    const actions = []
    for (let i = 0; i < 5; i++) {
      store.cycleEdgeModification(1, 2, 'Rue de Test')
      actions.push(store.getEdgeModification(1, 2))
    }
    expect(actions).toEqual(['remove', 'speed50', 'speed30', 'speed10', null])
  })
  it('restores without the bulk arrays', () => {
    const store = useTrafficAnalysisStore()
    // a saved investigation that no longer keeps the results
    expect(() =>
      store.restoreState({
        isOpen: true,
        edgeModifications: [{ u: 1, v: 2, action: 'remove', name: 'Rue de Test' }],
        activeVisualization: 'none'
      })
    ).not.toThrow()

    expect(store.isOpen).toBe(true)
    expect(store.nodePairs).toEqual([])
    expect(store.originalEdgeUsage).toEqual([])
    expect(store.newEdgeUsage).toEqual([])
    expect(store.impactStatistics).toBeNull()
    expect(store.getEdgeModification(1, 2)).toBe('remove')
    expect(store.isRestoring).toBe(false)
  })

  it('restores the routing options when the state has them', () => {
    const store = useTrafficAnalysisStore()
    store.restoreState({
      isOpen: true,
      edgeModifications: [],
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
      area_id: 'lausanne',
      bbox: null,
      scc_fraction: 1,
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
      edgeModifications: [],
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

  it('drops the results and the modifications when the area changes', () => {
    const store = useTrafficAnalysisStore()
    const usage = makeUsage()
    store.setEdgeUsage(usage, usage, undefined, 20000)
    store.cycleEdgeModification(1, 2, 'Rue de Bourg')

    store.setArea(BERN)

    expect(store.area).toEqual(BERN)
    expect(store.areaId).toBeNull()
    expect(store.newEdgeUsage).toHaveLength(0)
    expect(store.edgeModificationsCount).toBe(0)
  })

  it('does nothing when the same circle is set again', () => {
    const store = useTrafficAnalysisStore()
    store.setArea(BERN)
    store.cycleEdgeModification(1, 2, 'a street')

    store.setArea({ ...BERN })

    expect(store.edgeModificationsCount).toBe(1)
  })

  it('caches the baseline per area', async () => {
    const store = useTrafficAnalysisStore()
    vi.mocked(fetchBaseline).mockImplementation(async (odPairs?: number) => ({
      total_routes: odPairs ?? 20000,
      od_pairs: odPairs ?? 20000,
      edge_usage: baselineRows(3)
    }))

    await store.getBaseline(20000)
    await store.getBaseline(20000)
    expect(fetchBaseline).toHaveBeenCalledTimes(1)

    // another area, same count: the numbers are not the same, ask again
    store.setArea(BERN)
    vi.mocked(fetchArea).mockResolvedValue(areaInfo(BERN_ID))
    await store.ensureArea()

    await store.getBaseline(20000)
    expect(fetchBaseline).toHaveBeenCalledTimes(2)
    expect(vi.mocked(fetchBaseline).mock.calls[1][1]).toBe(BERN_ID)
  })

  it('asks the server once for an area, and builds it when it is gone', async () => {
    const store = useTrafficAnalysisStore()
    store.setArea(BERN)
    vi.mocked(fetchArea).mockResolvedValue(areaInfo(BERN_ID))

    const [a, b] = await Promise.all([store.ensureArea(), store.ensureArea()])

    expect(a).toBe(BERN_ID)
    expect(b).toBe(BERN_ID)
    expect(fetchArea).toHaveBeenCalledTimes(1)
    expect(fetchArea).toHaveBeenCalledWith(BERN_ID)
    expect(createArea).not.toHaveBeenCalled()
    expect(store.areaId).toBe(BERN_ID)
    expect(store.isBuildingArea).toBe(false)

    // it was evicted: the next call builds it back from the geometry
    store.forgetAreaId()
    vi.mocked(fetchArea).mockRejectedValue(new ApiError('gone', 404, 'area_not_loaded'))
    vi.mocked(createArea).mockResolvedValue(areaInfo(BERN_ID))

    expect(await store.ensureArea()).toBe(BERN_ID)
    expect(createArea).toHaveBeenCalledWith(BERN)
  })

  it('keeps the error of a refused area and lets the next call try again', async () => {
    const store = useTrafficAnalysisStore()
    store.setArea(BERN)
    vi.mocked(fetchArea).mockRejectedValue(new ApiError('gone', 404, 'area_not_loaded'))
    vi.mocked(createArea).mockRejectedValue(
      new ApiError('not enough junctions here', 422, 'too_sparse')
    )

    await expect(store.ensureArea()).rejects.toThrow('not enough junctions')
    expect(store.areaError?.code).toBe('too_sparse')
    expect(store.isBuildingArea).toBe(false)

    vi.mocked(createArea).mockResolvedValue(areaInfo(BERN_ID))
    expect(await store.ensureArea()).toBe(BERN_ID)
    expect(store.areaError).toBeNull()
  })

  it('needs no area for the default city', async () => {
    const store = useTrafficAnalysisStore()
    expect(await store.ensureArea()).toBeNull()
    expect(fetchArea).not.toHaveBeenCalled()
  })

  it('restores an area without dropping the restored results', () => {
    const store = useTrafficAnalysisStore()
    const usage = makeUsage()

    store.restoreState({
      isOpen: true,
      activeVisualization: 'frequency',
      edgeModifications: [{ u: 1, v: 2, action: 'remove' }],
      newEdgeUsage: usage,
      originalEdgeUsage: usage,
      area: BERN
    })

    expect(store.area).toEqual(BERN)
    expect(store.newEdgeUsage).toHaveLength(usage.length)
    expect(store.edgeModificationsCount).toBe(1)
  })

  it('opens the picker on the current circle', () => {
    const store = useTrafficAnalysisStore()
    store.setArea(BERN)

    store.enterPickMode()

    expect(store.pickMode).toBe(true)
    expect(store.draftArea).toEqual(BERN)
    // a copy, so dragging does not change the area behind it
    expect(store.draftArea).not.toBe(store.area)
  })

  it('opens the picker where the map looks when there is no circle yet', () => {
    const store = useTrafficAnalysisStore()

    store.enterPickMode({ lon: 8.54, lat: 47.37 })

    expect(store.draftArea).toEqual({ kind: 'circle', lon: 8.54, lat: 47.37, radiusM: 3000 })
    expect(store.area).toBeNull()
  })

  it('keeps the draft out of the scenario until it is confirmed', () => {
    const store = useTrafficAnalysisStore()
    store.enterPickMode()
    store.moveDraft(7.44, 46.95)
    store.setDraftRadius(5000)

    store.exitPickMode(false)

    expect(store.pickMode).toBe(false)
    expect(store.draftArea).toBeNull()
    expect(store.area).toBeNull()
  })

  it('makes the draft the area when it is confirmed', () => {
    const store = useTrafficAnalysisStore()
    store.enterPickMode()
    store.moveDraft(7.44, 46.95)
    store.setDraftRadius(3000)

    store.exitPickMode(true)

    expect(store.pickMode).toBe(false)
    expect(store.area).toEqual(BERN)
  })

  it('goes back to the default city and closes the picker', () => {
    const store = useTrafficAnalysisStore()
    store.setArea(BERN)
    store.enterPickMode()

    store.useDefaultArea()

    expect(store.area).toBeNull()
    expect(store.pickMode).toBe(false)
  })
})
