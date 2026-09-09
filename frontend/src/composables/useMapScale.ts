/**
 * The map scale, as numbers instead of a MapLibre control.
 *
 * MapLibre's ScaleControl draws its own box in the corner of the map, with its
 * own border and its own padding, next to the legend but not part of it. This
 * gives the same reading (a bar and the distance it covers) as plain values,
 * so the legend can draw it in its own language.
 */

import type { Map as MapLibreMap } from 'maplibre-gl'
import { onUnmounted, ref, watch, type Ref } from 'vue'

export interface MapScale {
  /** how wide the bar is on screen */
  widthPx: number
  /** what that width covers on the ground, "500 m" or "2 km" */
  label: string
}

/** The widest the bar may get. The bar is shorter, it stops on a round number. */
const MAX_WIDTH_PX = 110

/**
 * The biggest round distance under this one: 1, 2, 3 or 5 times a power of ten.
 * Same steps as MapLibre, so the reading does not change from what people know.
 */
function roundDown(metres: number): number {
  const pow10 = Math.pow(10, Math.floor(Math.log10(metres)))
  const digit = metres / pow10
  if (digit >= 5) return 5 * pow10
  if (digit >= 3) return 3 * pow10
  if (digit >= 2) return 2 * pow10
  return pow10
}

function format(metres: number): string {
  return metres >= 1000 ? `${metres / 1000} km` : `${metres} m`
}

/** A live scale for this map. Recomputed when the camera moves, not per frame. */
export function useMapScale(map: Ref<MapLibreMap | undefined>): Ref<MapScale | null> {
  const scale = ref<MapScale | null>(null)
  let watched: MapLibreMap | null = null

  function update(): void {
    const current = watched
    if (!current) return

    // Along the middle of the map, so the reading matches what is under it.
    const y = current.getContainer().clientHeight / 2
    const left = current.unproject([0, y])
    const right = current.unproject([MAX_WIDTH_PX, y])
    const metres = left.distanceTo(right)
    if (!Number.isFinite(metres) || metres <= 0) return

    const round = roundDown(metres)
    const next = { widthPx: Math.round((MAX_WIDTH_PX * round) / metres), label: format(round) }
    // A pan does not change the scale. Only write when it really moved, so the
    // legend does not re-render on every frame of a drag.
    const now = scale.value
    if (now && now.widthPx === next.widthPx && now.label === next.label) return
    scale.value = next
  }

  function detach(): void {
    if (!watched) return
    watched.off('move', update)
    watched.off('resize', update)
    watched = null
  }

  watch(
    map,
    (current) => {
      detach()
      if (!current) {
        scale.value = null
        return
      }
      watched = current
      current.on('move', update)
      current.on('resize', update)
      update()
    },
    { immediate: true }
  )

  onUnmounted(detach)

  return scale
}
