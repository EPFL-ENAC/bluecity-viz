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
})
