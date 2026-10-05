/**
 * Keep the Model state in step with the options while the user sets them.
 *
 * Every option of the Model step changes what the map shows, so the Model
 * state is loaded again when one moves. The iteration slider fires fast, so a
 * change waits a moment for the next one. Only on the Model step: the
 * workbench open on the routing tool, no area being picked, the tool in its
 * initial model, and the area ready (while the server routes its trips there
 * is no Model state, the map shows the betweenness instead). In simulation
 * the options are frozen and the run loads the Model state itself.
 *
 * What it costs: free flow is a slice of the startup routes on the server,
 * the equilibrium model one MSA run the first time per option set. Both are
 * then cached on the server and in the store.
 */
import { ApiError } from '@/services/trafficAnalysis'
import { useScenarioStore } from '@/stores/scenario'
import { useStorylineStore } from '@/stores/storyline'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { computed, onScopeDispose, watch } from 'vue'

export const MODEL_PREVIEW_DELAY_MS = 250

export function useModelPreview(): void {
  const trafficStore = useTrafficAnalysisStore()
  const scenarioStore = useScenarioStore()
  const storyline = useStorylineStore()

  /** The option set to show, or null when the Model step is not on screen. */
  const wanted = computed(() =>
    scenarioStore.isOpen &&
    scenarioStore.activeTab === 'routing' &&
    !trafficStore.pickMode &&
    trafficStore.areaReady &&
    storyline.phaseOf('routing') === 'init'
      ? trafficStore.modelOptionsKey
      : null
  )

  async function load(): Promise<void> {
    try {
      await trafficStore.loadModelState()
    } catch (error) {
      // The server dropped the area since we built it: build it and try once more.
      if (!(error instanceof ApiError) || error.code !== 'area_not_loaded') {
        console.error('Failed to load the model:', error)
        return
      }
      trafficStore.forgetAreaId()
      await trafficStore.loadModelState().catch((again) => {
        console.error('Failed to load the model:', again)
      })
    }
  }

  let timer: ReturnType<typeof setTimeout> | null = null

  watch(
    wanted,
    (key) => {
      if (timer) clearTimeout(timer)
      timer = null
      if (key === null) return
      // Back on the Model step with the same options: the map already has it.
      if (trafficStore.hasModelState && !trafficStore.modelStale) return
      timer = setTimeout(() => {
        timer = null
        void load()
      }, MODEL_PREVIEW_DELAY_MS)
    },
    { immediate: true }
  )

  onScopeDispose(() => {
    if (timer) clearTimeout(timer)
  })
}
