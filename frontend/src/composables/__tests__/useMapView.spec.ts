import { useMapView } from '@/composables/useMapView'
import { useCVRPStore } from '@/stores/cvrp'
import { useScenarioStore } from '@/stores/scenario'
import { useTrafficAnalysisStore, type EdgeUsageStats } from '@/stores/trafficAnalysis'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

/** One row is enough, hasCalculatedRoutes only looks at the length. */
const ROWS: EdgeUsageStats[] = [{ u: 1, v: 2, count: 3, frequency: 3 }]

function withRouting() {
  useTrafficAnalysisStore().originalEdgeUsage = ROWS
}

function withCvrp() {
  // hasResult only asks whether there is a result object.
  useCVRPStore().lastResult = { n_routes: 2 } as never
}

describe('useMapView', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('shows nothing and dims nothing before a run', () => {
    const view = useMapView()
    expect(view.activeHasResult.value).toBe(false)
    expect(view.shown.value).toBeNull()
    expect(view.dimmed.value).toBeNull()
  })

  it('draws the routing result and dims the scenario block', () => {
    withRouting()
    useScenarioStore().mapMode = 'result'
    const view = useMapView()
    expect(view.shown.value).toBe('routing')
    expect(view.dimmed.value).toBe('scenario')
  })

  it('dims the tool when the scenario is the lit zone', () => {
    withRouting()
    useScenarioStore().mapMode = 'scenario'
    const view = useMapView()
    expect(view.shown.value).toBeNull()
    expect(view.dimmed.value).toBe('tool')
  })

  it('draws one tool at a time, the one whose tab is open', () => {
    withRouting()
    withCvrp()
    const scenario = useScenarioStore()
    scenario.mapMode = 'result'
    const view = useMapView()
    expect(view.shown.value).toBe('routing')
    scenario.activeTab = 'cvrp'
    expect(view.shown.value).toBe('cvrp')
  })

  it('falls back to the scenario on a tab that has not run', () => {
    withRouting()
    const scenario = useScenarioStore()
    scenario.mapMode = 'result'
    scenario.activeTab = 'cvrp'
    const view = useMapView()
    expect(view.shown.value).toBeNull()
    // nothing to compete with, so the dock stays full ink
    expect(view.dimmed.value).toBeNull()
  })
})
