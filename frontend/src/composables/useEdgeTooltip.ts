import { shallowRef } from 'vue'

/** What the edge tooltip shows. The position is not in here on purpose: it
 *  changes at pointer rate and would re-render the component every frame. */
export interface EdgeTooltipData {
  key: string
  name: string
  highway?: string
  length?: number
  travel_time?: number
  speed_kph?: number
  bus_route_refs?: string
  // Route calculation stats (when available)
  frequency?: number
  count?: number
  delta_count?: number
  co2_per_km?: number
  co2_total?: number
  co2_delta?: number
  betweenness_centrality?: number
  delta_betweenness?: number
}

/** Moves the tooltip element. Registered by the component that renders it. */
export type TooltipMover = (x: number, y: number) => void

/**
 * Tooltip state split in two: the content is reactive and only changes when
 * the cursor enters a different edge, the position goes straight to the
 * element's style through a callback.
 */
export function useEdgeTooltip() {
  const tooltipData = shallowRef<EdgeTooltipData | null>(null)
  let mover: TooltipMover | null = null

  function setTooltipMover(fn: TooltipMover | null): void {
    mover = fn
  }

  function moveTooltip(x: number, y: number): void {
    mover?.(x, y)
  }

  /** Replace the content, but only when it is really another edge. */
  function setTooltip(data: EdgeTooltipData | null): boolean {
    const current = tooltipData.value
    if (data === null) {
      if (current === null) return false
      tooltipData.value = null
      return true
    }
    if (current && current.key === data.key) return false
    tooltipData.value = data
    return true
  }

  return { tooltipData, setTooltip, setTooltipMover, moveTooltip }
}
