import { useMapView } from '@/composables/useMapView'
import { useCVRPStore } from '@/stores/cvrp'
import { useScenarioStore } from '@/stores/scenario'
import { useStorylineStore } from '@/stores/storyline'
import { useTrafficAnalysisStore, type EdgeUsageStats } from '@/stores/trafficAnalysis'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

/** One row is enough, hasCalculatedRoutes only looks at the length. */
const ROWS: EdgeUsageStats[] = [{ u: 1, v: 2, count: 3, frequency: 3 }]

function withRouting() {
  useTrafficAnalysisStore().originalEdgeUsage = ROWS
}

function withModelState() {
  useTrafficAnalysisStore().modelUsage = ROWS
}

/** A drawn area the server is still routing, with its betweenness in. */
function withBuildingArea() {
  const store = useTrafficAnalysisStore()
  store.area = { kind: 'circle', lon: 7.44, lat: 46.95, radiusM: 3000 }
  store.areaInfo = { id: 'c_7.4400_46.9500_3000', ready: false } as never
  store.areaBetweenness = [{ u: 1, v: 2, betweenness_centrality: 5 }]
}

function withCvrp() {
  // hasResult only asks whether there is a result object.
  useCVRPStore().lastResult = { n_routes: 2 } as never
}

describe('useMapView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    // jsdom has no localStorage, the storyline store saves its phase there
    vi.stubGlobal('localStorage', { getItem: () => null, setItem: () => {} })
    // every case below is about an open workbench in the simulation phase,
    // unless it says otherwise
    useScenarioStore().isOpen = true
    useStorylineStore().validate('routing')
  })

  it('shows nothing and stays on the Scenario step before a run', () => {
    const view = useMapView()
    expect(view.activeHasResult.value).toBe(false)
    expect(view.shown.value).toBeNull()
    expect(view.step.value).toBe('scenario')
    // the Results step cannot open with nothing to read
    useScenarioStore().mapMode = 'result'
    expect(view.step.value).toBe('scenario')
  })

  it('draws the routing result on the Results step', () => {
    withRouting()
    useScenarioStore().mapMode = 'result'
    const view = useMapView()
    expect(view.shown.value).toBe('routing')
    expect(view.step.value).toBe('results')
  })

  it('draws the ink scenario on the Scenario step, even with a result', () => {
    withRouting()
    useScenarioStore().mapMode = 'scenario'
    const view = useMapView()
    expect(view.shown.value).toBeNull()
    expect(view.step.value).toBe('scenario')
  })

  it('draws one tool at a time, the one whose tab is open', () => {
    withRouting()
    withCvrp()
    const scenario = useScenarioStore()
    scenario.mapMode = 'result'
    useStorylineStore().validate('cvrp')
    const view = useMapView()
    expect(view.shown.value).toBe('routing')
    scenario.activeTab = 'cvrp'
    expect(view.shown.value).toBe('cvrp')
  })

  it('shows nothing once the workbench is closed', () => {
    withRouting()
    const scenario = useScenarioStore()
    scenario.mapMode = 'result'
    const view = useMapView()
    expect(view.shown.value).toBe('routing')
    scenario.isOpen = false
    expect(view.shown.value).toBeNull()
  })

  it('falls back to the scenario on a tab that has not run', () => {
    withRouting()
    const scenario = useScenarioStore()
    scenario.mapMode = 'result'
    scenario.activeTab = 'cvrp'
    const view = useMapView()
    expect(view.shown.value).toBeNull()
    // the CVRP model is not validated yet
    expect(view.step.value).toBe('model')
    useStorylineStore().validate('cvrp')
    expect(view.step.value).toBe('scenario')
  })

  it('draws the Model state on the Model step, read only', () => {
    useStorylineStore().phases.routing = 'init'
    const view = useMapView()
    // nothing loaded yet: the base network, nothing to point at
    expect(view.shown.value).toBeNull()
    expect(view.inspectable.value).toBe(false)

    withModelState()
    expect(view.phase.value).toBe('init')
    expect(view.shown.value).toBe('routing')
    expect(view.step.value).toBe('model')
    expect(view.editable.value).toBe(false)
    expect(view.inspectable.value).toBe(true)
  })

  it('draws the Model state in the initial model, whatever mapMode says', () => {
    withRouting()
    useScenarioStore().mapMode = 'scenario'
    // set after the rows, or the store moves the tool to simulation again
    useStorylineStore().phases.routing = 'init'
    const view = useMapView()
    expect(view.shown.value).toBeNull()

    withModelState()
    expect(view.shown.value).toBe('routing')
  })

  it('draws no Model state for the waste tool, nor while picking an area', () => {
    withModelState()
    useStorylineStore().phases.routing = 'init'
    const scenario = useScenarioStore()
    const view = useMapView()

    scenario.activeTab = 'cvrp'
    expect(view.shown.value).toBeNull()
    expect(view.inspectable.value).toBe(false)
    scenario.activeTab = 'routing'

    useTrafficAnalysisStore().pickMode = true
    expect(view.shown.value).toBeNull()
    expect(view.inspectable.value).toBe(false)
  })

  it('keeps the Model state off the map in simulation until a run', () => {
    withModelState()
    const view = useMapView()
    expect(view.phase.value).toBe('simulation')
    expect(view.shown.value).toBeNull()
    expect(view.step.value).toBe('scenario')
    expect(view.inspectable.value).toBe(true)
  })

  it('lets the pointer edit the graph only in simulation, open and not picking', () => {
    const view = useMapView()
    expect(view.editable.value).toBe(true)

    const storyline = useStorylineStore()
    storyline.phases.routing = 'init'
    expect(view.editable.value).toBe(false)
    storyline.validate('routing')
    expect(view.editable.value).toBe(true)

    useTrafficAnalysisStore().pickMode = true
    expect(view.editable.value).toBe(false)
    useTrafficAnalysisStore().pickMode = false

    useScenarioStore().isOpen = false
    expect(view.editable.value).toBe(false)
  })

  it('follows the phase of the tab it is on', () => {
    const view = useMapView()
    expect(view.editable.value).toBe(true)
    useScenarioStore().activeTab = 'cvrp'
    expect(view.phase.value).toBe('init')
    expect(view.editable.value).toBe(false)
  })

  it('draws the betweenness of an area still building, in any step and phase', () => {
    withBuildingArea()
    const view = useMapView()
    expect(view.shown.value).toBe('betweenness')
    // the step and the pointer do not change for it
    expect(view.step.value).toBe('scenario')
    expect(view.editable.value).toBe(true)

    useStorylineStore().phases.routing = 'init'
    expect(view.shown.value).toBe('betweenness')
    expect(view.step.value).toBe('model')
  })

  it('stops drawing the betweenness once the area is ready', () => {
    withBuildingArea()
    const view = useMapView()
    const store = useTrafficAnalysisStore()
    store.areaInfo = { id: 'c_7.4400_46.9500_3000', ready: true } as never
    expect(view.shown.value).toBeNull()
  })

  it('needs the rows, an open workbench, no picker and the routing tab', () => {
    withBuildingArea()
    const view = useMapView()
    const store = useTrafficAnalysisStore()
    const scenario = useScenarioStore()

    store.pickMode = true
    expect(view.shown.value).toBeNull()
    store.pickMode = false

    scenario.isOpen = false
    expect(view.shown.value).toBeNull()
    scenario.isOpen = true

    scenario.activeTab = 'cvrp'
    expect(view.shown.value).toBeNull()
    scenario.activeTab = 'routing'

    store.areaBetweenness = []
    expect(view.shown.value).toBeNull()
  })

  it('lets the Model state win over the betweenness on the Model step', () => {
    withBuildingArea()
    useStorylineStore().phases.routing = 'init'
    const view = useMapView()
    expect(view.shown.value).toBe('betweenness')
    withModelState()
    expect(view.shown.value).toBe('routing')
  })

  it('lets a restored result win over the betweenness', () => {
    withBuildingArea()
    withRouting()
    useScenarioStore().mapMode = 'result'
    expect(useMapView().shown.value).toBe('routing')
  })
})
