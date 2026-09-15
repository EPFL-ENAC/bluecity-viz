import { topAbsorbers, valueOf } from '@/composables/useResultStates'
import { useScenarioStore } from '@/stores/scenario'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { computed } from 'vue'

/**
 * The Δ bars of the dock.
 *
 * Two lists carry them: the modified streets (in the Simulation block) and the
 * streets that absorbed the traffic (in the Visualisation block). They are in
 * two components but share one scale, so a bar means the same length in both.
 */

export interface DeltaRow {
  key: string
  value: number
  color: string
}

export function useDeltaBars() {
  const trafficStore = useTrafficAnalysisStore()
  const scenarioStore = useScenarioStore()

  // Once a result exists the rows carry a Δ bar in the same colour as the map.
  const totalsByKey = computed(() => {
    const map = new Map<string, (typeof trafficStore.resultTotals)[number]>()
    for (const row of trafficStore.resultTotals) map.set(row.key, row)
    return map
  })

  // The bars read the routing result, so they follow the tab, not the lit zone.
  const showDelta = computed(
    () =>
      scenarioStore.activeTab === 'routing' &&
      trafficStore.hasCalculatedRoutes &&
      trafficStore.activeVisualization !== 'none'
  )

  function deltaRow(key: string): DeltaRow | null {
    const totals = totalsByKey.value.get(key)
    if (!totals || !showDelta.value) return null
    const value = valueOf(totals, trafficStore.activeVisualization as never)
    const [r, g, b] = trafficStore.getColor(value)
    return { key, value, color: `rgb(${r},${g},${b})` }
  }

  const modifiedRows = computed<DeltaRow[]>(() =>
    scenarioStore.list.map((edge) => deltaRow(edge.key)).filter((row): row is DeltaRow => !!row)
  )

  /** Where the traffic went: the untouched streets that gained the most. */
  const absorbers = computed(() => {
    if (!showDelta.value) return []
    const modified = new Set(scenarioStore.edgeModifications.keys())
    return topAbsorbers(trafficStore.resultTotals, modified).map((row) => {
      const value = valueOf(row, trafficStore.activeVisualization as never)
      const [r, g, b] = trafficStore.getColor(value)
      return { key: row.key, name: row.name, value, color: `rgb(${r},${g},${b})` }
    })
  })

  /** The widest value on screen, so the bars share one scale. */
  const barMax = computed(() => {
    let max = 0
    for (const row of [...modifiedRows.value, ...absorbers.value]) {
      max = Math.max(max, Math.abs(row.value))
    }
    return max || 1
  })

  function barWidth(value: number): string {
    return `${Math.min(100, (Math.abs(value) / barMax.value) * 100)}%`
  }

  function deltaText(value: number): string {
    const sign = value > 0 ? '+' : ''
    return `${sign}${Math.round(value)
      .toLocaleString('fr-CH')
      .replace(/[\u202f\u00a0\u2009]/g, ' ')}`
  }

  function rowFor(key: string): DeltaRow | null {
    return modifiedRows.value.find((row) => row.key === key) ?? null
  }

  return { showDelta, modifiedRows, absorbers, rowFor, barWidth, deltaText }
}
