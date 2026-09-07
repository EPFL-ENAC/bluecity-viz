import {
  EXPECTED_PUBLIC_KEYS,
  EXPECTED_SCALES,
  EXPECTED_STATE_KEYS,
  makeUsage
} from '@/stores/__tests__/fixtures/trafficScales'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

type Mode = (typeof EXPECTED_SCALES.modes)[number]

describe('traffic analysis store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
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

})
