/**
 * What the map shows, and which half of the dock is lit.
 *
 * The dock has two zones: the scenario (the modified edges) on top, the tool
 * (the tabs and their body) below. Exactly one is lit, and the map draws that
 * one: the ink scenario, or the active tab's result. The other zone is dimmed,
 * which is what tells the user it is not on the map right now.
 *
 * `scenarioStore.mapMode` holds which zone is lit. Everything else here is
 * derived, so there is one place to ask "what is on the map".
 */
import { useCVRPStore } from '@/stores/cvrp'
import { useScenarioStore } from '@/stores/scenario'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { computed, type ComputedRef } from 'vue'

/** The tool whose result is drawn, or null when the map shows the ink scenario. */
export type ShownResult = 'routing' | 'cvrp' | null

/** The dock zone drawn at 40 %, or null when neither is. */
export type DimmedZone = 'scenario' | 'tool' | null

export interface MapView {
  activeHasResult: ComputedRef<boolean>
  shown: ComputedRef<ShownResult>
  dimmed: ComputedRef<DimmedZone>
}

export function useMapView(): MapView {
  const scenarioStore = useScenarioStore()
  const trafficStore = useTrafficAnalysisStore()
  const cvrpStore = useCVRPStore()

  /** Only the tab you are on counts, the other tool never draws. */
  const activeHasResult = computed(() =>
    scenarioStore.activeTab === 'cvrp' ? cvrpStore.hasResult : trafficStore.hasCalculatedRoutes
  )

  const shown = computed<ShownResult>(() =>
    scenarioStore.mapMode === 'result' && activeHasResult.value ? scenarioStore.activeTab : null
  )

  // Nothing to compete with means nothing to dim: with no result the map can
  // only show the scenario, so both zones stay full ink.
  const dimmed = computed<DimmedZone>(() => {
    if (!activeHasResult.value) return null
    return scenarioStore.mapMode === 'result' ? 'scenario' : 'tool'
  })

  return { activeHasResult, shown, dimmed }
}
