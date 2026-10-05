import { MODEL_PREVIEW_DELAY_MS, useModelPreview } from '@/composables/useModelPreview'
import {
  ApiError,
  areaKey,
  createArea,
  fetchBaseline,
  type AreaInfo,
  type AreaSelection
} from '@/services/trafficAnalysis'
import { useScenarioStore } from '@/stores/scenario'
import { useStorylineStore } from '@/stores/storyline'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope, nextTick, type EffectScope } from 'vue'

// vi.mock is hoisted above the imports, so the factory cannot use anything
// declared here. importActual keeps the rest of the module real.
vi.mock('@/services/trafficAnalysis', async () => ({
  ...(await vi.importActual<typeof import('@/services/trafficAnalysis')>(
    '@/services/trafficAnalysis'
  )),
  fetchBaseline: vi.fn(),
  createArea: vi.fn()
}))

function answer() {
  return {
    total_routes: 20000,
    od_pairs: 20000,
    edge_usage: [{ u: 1, v: 2, count: 3, frequency: 1, co2_g_per_km: 5 }]
  }
}

/** Let the debounce fire and the fetch land. */
async function settle() {
  await vi.advanceTimersByTimeAsync(MODEL_PREVIEW_DELAY_MS)
  await vi.runAllTimersAsync()
}

describe('useModelPreview', () => {
  let scope: EffectScope

  beforeEach(() => {
    vi.useFakeTimers()
    setActivePinia(createPinia())
    // jsdom has no localStorage, the storyline store saves its phase there
    vi.stubGlobal('localStorage', { getItem: () => null, setItem: () => {} })
    vi.mocked(fetchBaseline).mockReset()
    vi.mocked(fetchBaseline).mockResolvedValue(answer())
    // every area is built first, the default one too, and the server mints
    // the same id as areaKey
    vi.mocked(createArea).mockImplementation(
      async (area: AreaSelection) => ({ id: areaKey(area) }) as AreaInfo
    )
    // the Model step of the routing tool, open
    useScenarioStore().isOpen = true
    scope = effectScope()
  })

  afterEach(() => {
    scope.stop()
    vi.useRealTimers()
  })

  it('loads the Model state once the Model step is on screen', async () => {
    scope.run(useModelPreview)
    expect(fetchBaseline).not.toHaveBeenCalled()

    await settle()
    expect(fetchBaseline).toHaveBeenCalledTimes(1)
    expect(useTrafficAnalysisStore().hasModelState).toBe(true)
  })

  it('asks once after a burst of changes, for the last options', async () => {
    const store = useTrafficAnalysisStore()
    scope.run(useModelPreview)
    await settle()
    vi.mocked(fetchBaseline).mockClear()

    // the iteration slider fires on every step it crosses
    store.useCongestionModel = true
    await nextTick()
    store.congestionIterations = 2
    await nextTick()
    store.congestionIterations = 3
    await nextTick()
    await settle()

    expect(fetchBaseline).toHaveBeenCalledTimes(1)
    expect(vi.mocked(fetchBaseline).mock.calls[0][3]).toBe(3)
    expect(store.modelStale).toBe(false)
  })

  it('asks nothing for elastic demand, the Model state does not depend on it', async () => {
    const store = useTrafficAnalysisStore()
    scope.run(useModelPreview)
    await settle()
    vi.mocked(fetchBaseline).mockClear()

    store.elasticDemand = true
    await nextTick()
    await settle()

    expect(fetchBaseline).not.toHaveBeenCalled()
  })

  it('asks nothing in simulation, the run loads the Model state itself', async () => {
    const store = useTrafficAnalysisStore()
    useStorylineStore().validate('routing')
    scope.run(useModelPreview)

    store.useCongestionModel = true
    await nextTick()
    await settle()

    expect(fetchBaseline).not.toHaveBeenCalled()
  })

  it('asks nothing again when the user comes back to the same options', async () => {
    const storyline = useStorylineStore()
    scope.run(useModelPreview)
    await settle()
    vi.mocked(fetchBaseline).mockClear()

    storyline.validate('routing')
    await nextTick()
    storyline.returnToInit('routing')
    await nextTick()
    await settle()

    expect(fetchBaseline).not.toHaveBeenCalled()
  })

  it('asks nothing on another tool, nor with the workbench closed', async () => {
    const scenario = useScenarioStore()
    scenario.activeTab = 'cvrp'
    scope.run(useModelPreview)
    await settle()

    scenario.activeTab = 'routing'
    scenario.isOpen = false
    await nextTick()
    await settle()

    expect(fetchBaseline).not.toHaveBeenCalled()
  })

  it('builds the area again and retries once when the server dropped it', async () => {
    vi.mocked(fetchBaseline)
      .mockRejectedValueOnce(new ApiError('gone', 404, 'area_not_loaded'))
      .mockResolvedValueOnce(answer())
    const forget = vi.spyOn(useTrafficAnalysisStore(), 'forgetAreaId')
    scope.run(useModelPreview)
    await settle()

    expect(forget).toHaveBeenCalledTimes(1)
    expect(fetchBaseline).toHaveBeenCalledTimes(2)
    expect(useTrafficAnalysisStore().modelError).toBeNull()
  })

  it('forgets a pending load when the dock goes away', async () => {
    scope.run(useModelPreview)
    scope.stop()
    await settle()

    expect(fetchBaseline).not.toHaveBeenCalled()
  })

  it('waits for an area the server is still building, then loads it', async () => {
    const store = useTrafficAnalysisStore()
    store.area = { kind: 'circle', lon: 7.44, lat: 46.95, radiusM: 3000 }
    store.areaId = 'c_7.4400_46.9500_3000'
    store.areaInfo = { id: 'c_7.4400_46.9500_3000', ready: false } as never
    scope.run(useModelPreview)

    await settle()
    // no Model state to ask for yet, and no error in the dock
    expect(fetchBaseline).not.toHaveBeenCalled()
    expect(store.modelError).toBeNull()

    store.areaInfo = { id: 'c_7.4400_46.9500_3000', ready: true } as never
    await settle()
    expect(fetchBaseline).toHaveBeenCalledTimes(1)
    expect(store.hasModelState).toBe(true)
  })
})
