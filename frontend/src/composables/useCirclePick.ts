/**
 * The pointer of the circle mode of the area picker: drag the circle, or click
 * where it should go. The picker overlay owns the map, the source and the
 * network canvas; this is only what the mouse does to the draft circle, and
 * the name of the place under it.
 */
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { AREA_FILL_LAYER } from '@/utils/areaCircle'
import { areaLabel, collectPlaces, type PlacePoint } from '@/utils/areaName'
import type { Map as MapLibreMap, MapMouseEvent } from 'maplibre-gl'
import { watch, type ComputedRef } from 'vue'

export interface PickMode {
  attach(map: MapLibreMap): void
  detach(map: MapLibreMap): void
}

export function useCirclePick(options: {
  map: ComputedRef<MapLibreMap | undefined>
  invalidate: () => void
  checkNow: () => void
}): PickMode {
  const { map, invalidate, checkNow } = options
  const trafficStore = useTrafficAnalysisStore()

  let attached = false
  let dragging = false
  // Where the button went down, to tell a click from the end of a drag.
  let downAt: { x: number; y: number } | null = null
  // The towns of the loaded tiles, read once per camera stop. The drag itself
  // then only runs the naming, which is arithmetic on this list.
  let places: PlacePoint[] = []

  /** Read the towns again, the map has new tiles. */
  function readPlaces(): void {
    const current = map.value
    if (!current) return
    places = collectPlaces(current)
    nameDraft()
  }

  /** Put the name of the place under the circle in the draft. */
  function nameDraft(): void {
    const circle = trafficStore.draftArea
    if (attached && circle?.kind === 'circle') {
      trafficStore.setDraftName(areaLabel(circle, places))
    }
  }

  function overCircle(current: MapLibreMap, event: MapMouseEvent): boolean {
    if (!current.getLayer(AREA_FILL_LAYER)) return false
    return current.queryRenderedFeatures(event.point, { layers: [AREA_FILL_LAYER] }).length > 0
  }

  function onMouseDown(event: MapMouseEvent): void {
    const current = map.value
    if (!current) return
    downAt = { x: event.point.x, y: event.point.y }
    if (!overCircle(current, event)) return
    event.preventDefault()
    dragging = true
    current.dragPan.disable()
    current.getCanvas().style.cursor = 'grabbing'
  }

  function onMouseMove(event: MapMouseEvent): void {
    const current = map.value
    if (!current) return
    if (!dragging) {
      current.getCanvas().style.cursor = overCircle(current, event) ? 'grab' : ''
      return
    }
    trafficStore.moveDraft(event.lngLat.lng, event.lngLat.lat)
    invalidate()
  }

  function onMouseUp(): void {
    const current = map.value
    if (!dragging || !current) return
    dragging = false
    current.dragPan.enable()
    current.getCanvas().style.cursor = 'grab'
    // Same circle means the same key, and checkNow answers from what it has.
    checkNow()
  }

  /**
   * A click away from the circle moves it there, so no long drag is needed.
   *
   * A drag ends with a click too, and MapLibre does not always send it, so a
   * flag set during the drag would stay on and eat the next real click. The
   * distance from the button going down says it: a click does not move.
   */
  function onClick(event: MapMouseEvent): void {
    const from = downAt
    downAt = null
    if (from) {
      const dx = event.point.x - from.x
      const dy = event.point.y - from.y
      if (dx * dx + dy * dy > 9) return
    }
    trafficStore.moveDraft(event.lngLat.lng, event.lngLat.lat)
    invalidate()
    checkNow()
  }

  // The circle moved or grew: same towns, new answer.
  watch(() => {
    const draft = trafficStore.draftArea
    return draft?.kind === 'circle' ? [draft.lon, draft.lat, draft.radiusM] : null
  }, nameDraft)

  // The radius slider moves the circle without a drag, check that one too.
  watch(
    () => (trafficStore.draftArea?.kind === 'circle' ? trafficStore.draftArea.radiusM : undefined),
    (radius, previous) => {
      if (!attached || radius === undefined || previous === undefined) return
      invalidate()
      checkNow()
    }
  )

  function attach(current: MapLibreMap): void {
    if (attached) return
    attached = true
    current.on('mousedown', onMouseDown)
    current.on('mousemove', onMouseMove)
    current.on('mouseup', onMouseUp)
    current.on('click', onClick)
    current.on('idle', readPlaces)
    readPlaces()
  }

  function detach(current: MapLibreMap): void {
    if (!attached) return
    attached = false
    downAt = null
    dragging = false
    current.off('mousedown', onMouseDown)
    current.off('mousemove', onMouseMove)
    current.off('mouseup', onMouseUp)
    current.off('click', onClick)
    current.off('idle', readPlaces)
    current.dragPan.enable()
    current.getCanvas().style.cursor = ''
  }

  return { attach, detach }
}
