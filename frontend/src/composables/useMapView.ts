/**
 * What the map shows, which step of the dock is open, and whether the graph can
 * be edited.
 *
 * Each tool is a storyline of three steps: Model, Scenario, Results. Only one
 * is open, and the map draws what that step is about: the base network, the
 * ink scenario, or the tool's result.
 *
 * Two pieces of state decide it. The phase (stores/storyline.ts): in `init`
 * the user sets the model, the graph is read only and no result is drawn. In
 * `simulation` the network opens for editing. Then `scenarioStore.mapMode`
 * says whether the Scenario or the Results step is open. Everything else here
 * is derived, so there is one place to ask "what is on the map".
 */
import { useCVRPStore } from '@/stores/cvrp'
import { useScenarioStore } from '@/stores/scenario'
import { useStorylineStore, type StoryPhase } from '@/stores/storyline'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { computed, type ComputedRef } from 'vue'

/** The tool whose result is drawn, or null when the map shows the ink scenario. */
export type ShownResult = 'routing' | 'cvrp' | null

/** The open step of the tool's storyline. */
export type StoryStepName = 'model' | 'scenario' | 'results'

export interface MapView {
  activeHasResult: ComputedRef<boolean>
  phase: ComputedRef<StoryPhase>
  editable: ComputedRef<boolean>
  shown: ComputedRef<ShownResult>
  step: ComputedRef<StoryStepName>
}

export function useMapView(): MapView {
  const scenarioStore = useScenarioStore()
  const trafficStore = useTrafficAnalysisStore()
  const cvrpStore = useCVRPStore()
  const storyline = useStorylineStore()

  /** Only the tab you are on counts, the other tool never draws. */
  const activeHasResult = computed(() =>
    scenarioStore.activeTab === 'cvrp' ? cvrpStore.hasResult : trafficStore.hasCalculatedRoutes
  )

  /** The phase of the tab you are on. */
  const phase = computed<StoryPhase>(() => storyline.phaseOf(scenarioStore.activeTab))

  // The pointer edits the graph only once the model is validated. Before that
  // the graph is a picture of the base network: no hover card, no popover, no
  // lasso. Picking an area owns the pointer too.
  const editable = computed(
    () => scenarioStore.isOpen && !trafficStore.pickMode && phase.value === 'simulation'
  )

  // Closing the workbench takes the overlay off the map, so nothing is shown
  // and the legend has nothing to explain. Picking an area does the same: the
  // map is the whole country then, and the result belongs to the old one.
  const shown = computed<ShownResult>(() =>
    scenarioStore.isOpen &&
    !trafficStore.pickMode &&
    phase.value === 'simulation' &&
    scenarioStore.mapMode === 'result' &&
    activeHasResult.value
      ? scenarioStore.activeTab
      : null
  )

  // The Results step opens only when there is a result to read. Without one
  // the user is on the Scenario step, whatever mapMode says.
  const step = computed<StoryStepName>(() => {
    if (phase.value !== 'simulation') return 'model'
    return scenarioStore.mapMode === 'result' && activeHasResult.value ? 'results' : 'scenario'
  })

  return { activeHasResult, phase, editable, shown, step }
}
