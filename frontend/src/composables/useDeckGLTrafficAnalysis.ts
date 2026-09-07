import { buildEdgeColors, buildRouteLayers, type RouteEdge } from '@/composables/buildTrafficLayers'
import { useEdgeTooltip, type EdgeTooltipData } from '@/composables/useEdgeTooltip'
import { edgeKey, useGraphEdges } from '@/composables/useGraphEdges'
import type { EdgeGeometry } from '@/services/trafficAnalysis'
import { useTrafficAnalysisStore, type EdgeUsageStats } from '@/stores/trafficAnalysis'
import { computed, shallowRef, watch } from 'vue'

export type { EdgeTooltipData }

/**
 * The deck.gl layers for the traffic analysis, and the edge interaction.
 *
 * Everything is derived: `layers` is a computed over the store, so a pointer
 * move that does not change the hovered edge re-runs nothing at all, and a
 * change of visualization mode only swaps a color buffer instead of rebuilding
 * the 6k paths.
 */
export function useDeckGLTrafficAnalysis() {
  const trafficStore = useTrafficAnalysisStore()
  const { edges, edgeMap, loadGraphEdges, getEdge, getReverseEdge } = useGraphEdges()
  const { tooltipData, setTooltip, setTooltipMover, moveTooltip } = useEdgeTooltip()

  const hoveredEdge = shallowRef<EdgeGeometry | null>(null)
  let hoveredKey: string | null = null
  let edgeClickCallback: ((u: number, v: number, name?: string) => void) | null = null

  // one color buffer per mode, thrown away when the numbers change
  let colorCache = new Map<string, Uint8Array>()
  let colorVersion = 0

  /** The stats of the last calculation, by edge key, for the tooltip. */
  const edgeStatsMap = computed(() => {
    const map = new Map<string, EdgeUsageStats>()
    for (const stat of trafficStore.newEdgeUsage) {
      map.set(edgeKey(stat.u, stat.v), stat)
    }
    return map
  })

  /**
   * The edges to color, geometry and numbers joined.
   *
   * Does not read activeVisualization, so switching mode keeps the same array
   * and deck keeps its buffers.
   */
  const displayEdges = computed<RouteEdge[]>(() => {
    const usage = trafficStore.newEdgeUsage
    const map = edgeMap.value
    if (usage.length === 0 || map.size === 0) return []

    const onlyBusRoutes = trafficStore.filterBusRoutes
    const out: RouteEdge[] = []

    for (const stat of usage) {
      const edge = map.get(edgeKey(stat.u, stat.v))
      if (!edge) continue
      if (onlyBusRoutes && (edge.bus_route_count ?? 0) === 0) continue

      const deltaFrequency = stat.delta_frequency ?? 0
      const co2PerKm = stat.co2_per_km ?? 0
      const origFreq = stat.frequency - deltaFrequency

      out.push({
        ...edge,
        frequency: stat.frequency,
        delta_count: stat.delta_count ?? 0,
        delta_frequency: deltaFrequency,
        co2_per_km: co2PerKm,
        count: stat.count,
        co2_total: co2PerKm * stat.count,
        co2_delta: co2PerKm * deltaFrequency,
        betweenness_centrality: stat.betweenness_centrality ?? 0,
        delta_betweenness: stat.delta_betweenness ?? 0,
        delta_relative: origFreq > 0.0001 ? (deltaFrequency / origFreq) * 100 : 0
      })
    }

    // draw the busy edges last so they end up on top
    out.sort((a, b) => a.frequency - b.frequency)

    // the numbers changed, the old colors do not apply
    colorCache = new Map()
    colorVersion++

    return out
  })

  function colorsFor(mode: string, list: RouteEdge[]): Uint8Array {
    let colors = colorCache.get(mode)
    if (!colors) {
      colors = buildEdgeColors(list, mode, trafficStore.getColor)
      colorCache.set(mode, colors)
    }
    return colors
  }

  // Only the coloured result is left here. The graph, the pointer and the
  // modifications are MapLibre layers now (utils/bluecityGraph.ts).
  const layers = computed<any[]>(() => {
    if (edges.value.length === 0) return []

    const mode = trafficStore.activeVisualization
    const list = displayEdges.value
    if (mode === 'none' || list.length === 0) return []

    return buildRouteLayers({
      edges: list,
      colors: colorsFor(mode, list),
      mode,
      colorVersion
    })
  })

  /** Click an edge to cycle its modification, both directions together. */
  function handleClick(info: any): void {
    if (!info.object || !edgeClickCallback) return

    const clicked = info.object.properties || info.object
    if (clicked.u === undefined || clicked.v === undefined) return

    edgeClickCallback(clicked.u, clicked.v, clicked.name || `Edge ${clicked.u}→${clicked.v}`)

    const reverse = getReverseEdge(clicked.u, clicked.v)
    if (reverse) {
      edgeClickCallback(reverse.u, reverse.v, reverse.name || `Edge ${reverse.u}→${reverse.v}`)
    }
  }

  function tooltipFor(key: string, hovered: any, edge?: EdgeGeometry): EdgeTooltipData {
    const stats = edgeStatsMap.value.get(key)

    const length = hovered.length ?? edge?.length
    const travelTime = hovered.travel_time ?? edge?.travel_time
    let speedKph: number | undefined
    if (length && travelTime && travelTime > 0) {
      speedKph = Math.round(length / 1000 / (travelTime / 3600)) // km/h
    }

    const co2PerKm = stats?.co2_per_km ?? hovered.co2_per_km
    const count = stats?.count ?? hovered.count
    const deltaFrequency = stats?.delta_frequency ?? hovered.delta_frequency

    return {
      key,
      name: hovered.name || edge?.name || `Edge ${hovered.u}→${hovered.v}`,
      highway: hovered.highway || edge?.highway,
      length,
      travel_time: travelTime,
      speed_kph: speedKph,
      bus_route_refs: hovered.bus_route_refs || edge?.bus_route_refs || undefined,
      frequency: stats?.frequency ?? hovered.frequency,
      count,
      delta_count: stats?.delta_count ?? hovered.delta_count,
      co2_per_km: co2PerKm,
      // computed here so the tooltip is the same whether the cursor hit the
      // grey network or a colored route
      co2_total: co2PerKm !== undefined && count !== undefined ? co2PerKm * count : undefined,
      co2_delta:
        co2PerKm !== undefined && deltaFrequency !== undefined
          ? co2PerKm * deltaFrequency
          : undefined,
      betweenness_centrality: stats?.betweenness_centrality ?? hovered.betweenness_centrality,
      delta_betweenness: stats?.delta_betweenness ?? hovered.delta_betweenness
    }
  }

  /**
   * Hover.
   *
   * Called once per animation frame by deck. The position always goes straight
   * to the element; the reactive content and the highlighted edge only change
   * when the cursor is on another edge, which is what keeps the basemap from
   * repainting on every move.
   */
  function handleHover(info: any): void {
    const hovered = info.object ? info.object.properties || info.object : null

    if (!hovered || hovered.u === undefined || hovered.v === undefined) {
      if (hoveredKey !== null) {
        hoveredKey = null
        hoveredEdge.value = null
        setTooltip(null)
      }
      return
    }

    const key = edgeKey(hovered.u, hovered.v)
    moveTooltip(info.x, info.y)

    if (key === hoveredKey) return

    hoveredKey = key
    const edge = getEdge(hovered.u, hovered.v)
    hoveredEdge.value = edge ?? null
    setTooltip(tooltipFor(key, hovered, edge))
  }

  /** Drop the highlight and the tooltip, e.g. when another tool takes over. */
  function clearHover(): void {
    if (hoveredKey === null) return
    hoveredKey = null
    hoveredEdge.value = null
    setTooltip(null)
  }

  // The tooltip must not outlive the numbers it shows. A new calculation, a
  // cleared result or a restored scenario replaces the stats, so drop what is
  // on screen; the next pointer move fills it again.
  watch(() => trafficStore.newEdgeUsage, clearHover)

  function setEdgeClickCallback(callback: (u: number, v: number, name?: string) => void): void {
    edgeClickCallback = callback
  }

  return {
    layers,
    tooltipData,
    edgeMap,
    loadGraphEdges,
    handleClick,
    handleHover,
    clearHover,
    setEdgeClickCallback,
    setTooltipMover
  }
}
