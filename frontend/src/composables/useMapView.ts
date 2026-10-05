/**
 * What the map shows, which step of the dock is open, and whether the graph can
 * be edited.
 *
 * Each tool is a storyline of three steps: Model, Scenario, Results. Only one
 * is open, and the map draws what that step is about: the model (the routing
 * it gives on the untouched network), the ink scenario, or the tool's result.
 *
 * Two pieces of state decide it. The phase (stores/storyline.ts): in `init`
 * the user sets the model, the graph is read only, and the routing tool draws
 * its Model state once it is loaded. In `simulation` the network opens for
 * editing. Then `scenarioStore.mapMode` says whether the Scenario or the
 * Results step is open. Everything else here is derived, so there is one
 * place to ask "what is on the map".
 *
 * One more case: while the server routes the trips of a new area, there is no
 * Model state yet, and the map shows the betweenness of its streets in any
 * step. It goes when the area is ready.
 */
import { useCVRPStore } from '@/stores/cvrp'
import { useScenarioStore } from '@/stores/scenario'
import { useStorylineStore, type StoryPhase } from '@/stores/storyline'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { computed, type ComputedRef } from 'vue'

/**
 * The tool whose result is drawn, the betweenness of an area still being
 * built, or null when the map shows the ink scenario.
 */
export type ShownResult = 'routing' | 'cvrp' | 'betweenness' | null

/** The open step of the tool's storyline. */
export type StoryStepName = 'model' | 'scenario' | 'results'

export interface MapView {
  activeHasResult: ComputedRef<boolean>
  phase: ComputedRef<StoryPhase>
  editable: ComputedRef<boolean>
  inspectable: ComputedRef<boolean>
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
  const shown = computed<ShownResult>(() => {
    if (!scenarioStore.isOpen || trafficStore.pickMode) return null
    // The Model step draws the routing of the chosen model. The waste tool
    // has no such state, its Model step stays the base network.
    const drawn =
      phase.value === 'init'
        ? scenarioStore.activeTab === 'routing' && trafficStore.hasModelState
          ? 'routing'
          : null
        : scenarioStore.mapMode === 'result' && activeHasResult.value
          ? scenarioStore.activeTab
          : null
    if (drawn) return drawn
    // An area still building has no Model state yet, but its betweenness is
    // there. A result restored with an investigation wins over it.
    if (
      scenarioStore.activeTab === 'routing' &&
      !trafficStore.areaReady &&
      trafficStore.areaBetweenness.length > 0
    )
      return 'betweenness'
    return null
  })

  // The pointer may read a street without editing it: in the Model step the
  // user checks the model on a street they know. Hover only, no click.
  const inspectable = computed(
    () => editable.value || (phase.value === 'init' && shown.value === 'routing')
  )

  // The Results step opens only when there is a result to read. Without one
  // the user is on the Scenario step, whatever mapMode says.
  const step = computed<StoryStepName>(() => {
    if (phase.value !== 'simulation') return 'model'
    return scenarioStore.mapMode === 'result' && activeHasResult.value ? 'results' : 'scenario'
  })

  return { activeHasResult, phase, editable, inspectable, shown, step }
}
