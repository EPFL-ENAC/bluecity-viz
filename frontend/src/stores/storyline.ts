import { useCVRPStore } from '@/stores/cvrp'
import { useScenarioStore } from '@/stores/scenario'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'

/**
 * Where each tool is in its storyline.
 *
 * `init`: the user sets the model options, nothing on the graph can be edited.
 * `simulation`: the options are frozen, the user edits the network and runs.
 *
 * A result only ever exists in `simulation`: going back to init drops it, and
 * a result that lands (a run, an investigation restored with its result) moves
 * the tool to simulation. The phase is per tool, not per investigation, and it
 * survives a reload in its own localStorage key.
 */

export type StoryPhase = 'init' | 'simulation'
export type StoryTool = 'routing' | 'cvrp'

export const STORYLINE_STORAGE_KEY = 'bluecity-storyline'

type Phases = Record<StoryTool, StoryPhase>

function defaults(): Phases {
  return { routing: 'init', cvrp: 'init' }
}

function asPhase(value: unknown): StoryPhase {
  return value === 'simulation' ? 'simulation' : 'init'
}

// jsdom in the unit tests has no localStorage global, so every access is in a
// try/catch, like the theme store.
function readStored(): Phases {
  try {
    const raw = localStorage.getItem(STORYLINE_STORAGE_KEY)
    if (!raw) return defaults()
    const parsed = JSON.parse(raw) as Partial<Record<StoryTool, unknown>> | null
    if (!parsed || typeof parsed !== 'object') return defaults()
    return { routing: asPhase(parsed.routing), cvrp: asPhase(parsed.cvrp) }
  } catch {
    return defaults()
  }
}

export const useStorylineStore = defineStore('storyline', () => {
  const phases = ref<Phases>(readStored())

  function phaseOf(tool: StoryTool): StoryPhase {
    return phases.value[tool]
  }

  /** The phase of the tab the user is on. */
  const current = computed<StoryPhase>(() => phases.value[useScenarioStore().activeTab])

  /** Validate the initial model: the options freeze, the network opens. */
  function validate(tool: StoryTool): void {
    phases.value = { ...phases.value, [tool]: 'simulation' }
  }

  /**
   * Back to the options. The result was computed with the options we are about
   * to change, so it goes. The modified edges stay, they are the scenario.
   */
  function returnToInit(tool: StoryTool): void {
    phases.value = { ...phases.value, [tool]: 'init' }
    if (tool === 'routing') useTrafficAnalysisStore().clearResults()
    else useCVRPStore().clearResult()
  }

  // A result means the tool is in simulation, whatever put it there.
  const trafficStore = useTrafficAnalysisStore()
  const cvrpStore = useCVRPStore()
  watch(
    () => trafficStore.hasCalculatedRoutes,
    (has) => {
      if (has && phases.value.routing !== 'simulation') validate('routing')
    },
    { immediate: true }
  )
  watch(
    () => cvrpStore.hasResult,
    (has) => {
      if (has && phases.value.cvrp !== 'simulation') validate('cvrp')
    },
    { immediate: true }
  )

  watch(phases, (next) => {
    try {
      localStorage.setItem(STORYLINE_STORAGE_KEY, JSON.stringify(next))
    } catch (error) {
      console.warn('Failed to save the storyline phase:', error)
    }
  })

  return { phases, current, phaseOf, validate, returnToInit }
})
