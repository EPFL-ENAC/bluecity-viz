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

  it('draws no result and opens the Model step in the initial model', () => {
    withRouting()
    const scenario = useScenarioStore()
    scenario.mapMode = 'result'
    const view = useMapView()
    expect(view.shown.value).toBe('routing')
    // set after the rows, or the store moves the tool to simulation again
    useStorylineStore().phases.routing = 'init'
    expect(view.phase.value).toBe('init')
    expect(view.shown.value).toBeNull()
    expect(view.step.value).toBe('model')
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
})
