import { useScenarioStore } from '@/stores/scenario'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { bbox, polylineIntersectsPolygon, polylineNearSegment, type Pt } from '@/utils/geometry'
import type { Map as MapLibreMap, MapMouseEvent } from 'maplibre-gl'
import { shallowRef, watch, type Ref } from 'vue'

/**
 * The two drag tools that pick several streets at once.
 *
 * The lasso draws a shape and takes every street it holds. The brush paints a
 * circle along the streets and takes what it touches. Both work in screen
 * pixels: the map is frozen while the button is down, so the streets are
 * projected once per step and tested flat.
 *
 * Neither writes a modification. They fill the selection, and the popover
 * that opens at the end of the stroke says what to do with it.
 */

/** What the overlay draws while a tool is in use. */
export type ToolShape =
  { kind: 'lasso'; points: Pt[] } | { kind: 'brush'; at: Pt; radius: number; trail: Pt[] }

/** The streets drawn inside a box, from useGraphOverlay. */
export type StreetsInBox = (
  box: [[number, number], [number, number]]
) => Array<{ key: string; coordinates: [number, number][] }>

/** A stray click is not a lasso: the shape has to be this wide, in pixels. */
const MIN_LASSO = 4

/** The brush box takes a couple of pixels more, for the street width. */
const BOX_MARGIN = 2

export function useSelectTools(
  mapRef: Ref<MapLibreMap | undefined>,
  streetsInBox: StreetsInBox,
  callbacks: { onDone?: (point: { x: number; y: number }) => void } = {}
) {
  const scenarioStore = useScenarioStore()
  const trafficStore = useTrafficAnalysisStore()

  /** null when no tool is drawing anything. */
  const shape = shallowRef<ToolShape | null>(null)

  /** Space held: the map pans instead of the tool drawing, like in Figma. */
  let paused = false
  let dragging = false
  let points: Pt[] = []
  let caught = 0
  let frame = 0
  let pending: Pt | null = null

  function project(coordinates: [number, number][], map: MapLibreMap): Pt[] {
    return coordinates.map((position) => {
      const point = map.project(position)
      return [point.x, point.y] as Pt
    })
  }

  /** One step of the brush: the streets under the circle as it slides. */
  function paint(map: MapLibreMap, from: Pt, to: Pt): void {
    const radius = scenarioStore.brushRadius
    const found: string[] = []

    for (const street of streetsInBox(bbox([from, to], radius + BOX_MARGIN))) {
      if (polylineNearSegment(project(street.coordinates, map), from, to, radius)) {
        found.push(street.key)
      }
    }

    if (found.length === 0) return
    caught += found.length
    scenarioStore.addSelected(found)
  }

  /** The end of a lasso: every street the shape holds or crosses. */
  function closeLasso(map: MapLibreMap): void {
    if (points.length < 3) return

    const box = bbox(points)
    const wide = box[1][0] - box[0][0] >= MIN_LASSO || box[1][1] - box[0][1] >= MIN_LASSO
    if (!wide) return

    const found: string[] = []
    for (const street of streetsInBox(box)) {
      if (polylineIntersectsPolygon(project(street.coordinates, map), points)) {
        found.push(street.key)
      }
    }

    if (found.length === 0) return
    caught += found.length
    scenarioStore.addSelected(found)
  }

  function onMouseDown(event: MapMouseEvent): void {
    const map = mapRef.value
    if (!map || !scenarioStore.isOpen || scenarioStore.tool === 'pointer') return
    // Picking an area owns the drag then, and it moves its own circle.
    if (trafficStore.pickMode) return
    // Space is held: this drag belongs to the map.
    if (paused) return

    // The map must not pan under the stroke.
    event.preventDefault()
    map.dragPan.disable()

    dragging = true
    caught = 0
    const at: Pt = [event.point.x, event.point.y]
    points = [at]

    if (scenarioStore.tool === 'lasso') {
      shape.value = { kind: 'lasso', points: [at] }
    } else {
      shape.value = { kind: 'brush', at, radius: scenarioStore.brushRadius, trail: [at] }
      paint(map, at, at)
    }
  }

  function onMouseMove(event: MapMouseEvent): void {
    if (scenarioStore.tool === 'pointer' || paused) return
    pending = [event.point.x, event.point.y]
    if (frame) return

    frame = requestAnimationFrame(() => {
      frame = 0
      const map = mapRef.value
      const at = pending
      if (!map || !at) return

      if (!dragging) {
        // The brush shows where it would paint, before the stroke starts.
        if (scenarioStore.tool === 'brush') {
          shape.value = { kind: 'brush', at, radius: scenarioStore.brushRadius, trail: [] }
        }
        return
      }

      const from = points[points.length - 1] ?? at
      points.push(at)

      if (scenarioStore.tool === 'lasso') {
        shape.value = { kind: 'lasso', points: [...points] }
      } else {
        paint(map, from, at)
        shape.value = { kind: 'brush', at, radius: scenarioStore.brushRadius, trail: [...points] }
      }
    })
  }

  /** End the stroke and apply it. `at` is null when the button went up off the map. */
  function stop(at: Pt | null): void {
    if (!dragging) return
    dragging = false
    if (frame) {
      cancelAnimationFrame(frame)
      frame = 0
    }

    const map = mapRef.value
    const tool = scenarioStore.tool

    if (map) {
      map.dragPan.enable()

      // The last move may not have had its frame yet, so take that sample now.
      if (at) {
        const from = points[points.length - 1] ?? at
        points.push(at)
        if (tool === 'brush') paint(map, from, at)
      }
      if (tool === 'lasso') closeLasso(map)
    }

    const end = points[points.length - 1]
    points = []
    shape.value =
      tool === 'brush' && end
        ? { kind: 'brush', at: end, radius: scenarioStore.brushRadius, trail: [] }
        : null

    // Nothing under the stroke, nothing to edit: no popover.
    if (caught > 0 && end) callbacks.onDone?.({ x: end[0], y: end[1] })
    caught = 0
  }

  /** Drop the stroke without applying it (the tool changed under it). */
  function cancel(): void {
    if (frame) {
      cancelAnimationFrame(frame)
      frame = 0
    }
    points = []
    caught = 0
    shape.value = null
    if (dragging) {
      dragging = false
      mapRef.value?.dragPan.enable()
    }
  }

  function onMouseUp(event: MapMouseEvent): void {
    stop([event.point.x, event.point.y])
  }

  function onWindowMouseUp(): void {
    stop(null)
  }

  function onMouseOut(): void {
    if (!dragging) shape.value = null
  }

  function cursorFor(tool: string): string {
    // Space held: the map is a plain map again, and says so.
    if (paused) return 'grab'
    if (tool === 'lasso') return 'crosshair'
    // The brush draws its own circle, the arrow would sit on top of it.
    if (tool === 'brush') return 'none'
    return ''
  }

  function setCursor(): void {
    const map = mapRef.value
    if (map) map.getCanvas().style.cursor = cursorFor(scenarioStore.tool)
  }

  /** Typing in a field is not a shortcut. */
  function isTyping(target: EventTarget | null): boolean {
    const el = target as HTMLElement | null
    if (!el || !el.tagName) return false
    const tag = el.tagName.toLowerCase()
    return tag === 'input' || tag === 'textarea' || tag === 'select' || el.isContentEditable
  }

  /**
   * Hold Space to pan without leaving the tool.
   *
   * Drawing takes the drag, so moving the map used to mean going back to the
   * pointer and picking the tool again. A stroke already under way is left
   * alone, only the next one goes to the map.
   */
  function onKeyDown(event: KeyboardEvent): void {
    if (event.code !== 'Space' || paused || isTyping(event.target)) return
    if (!scenarioStore.isOpen || scenarioStore.tool === 'pointer') return
    // Space on a focused button would press it.
    event.preventDefault()
    paused = true
    if (!dragging) shape.value = null
    setCursor()
  }

  function onKeyUp(event: KeyboardEvent): void {
    if (event.code !== 'Space' || !paused) return
    paused = false
    setCursor()
  }

  watch(
    () => scenarioStore.tool,
    () => {
      cancel()
      setCursor()
    }
  )

  // The workbench owns the tools. Closing it, going to pick an area, or
  // running a tool (the result lights, the scenario steps back) puts the
  // pointer back, so a drag on the map pans it again.
  watch(
    () => scenarioStore.isOpen && !trafficStore.pickMode && scenarioStore.mapMode === 'scenario',
    (live) => {
      if (!live) scenarioStore.tool = 'pointer'
    }
  )

  function attach(map: MapLibreMap): void {
    map.on('mousedown', onMouseDown)
    map.on('mousemove', onMouseMove)
    map.on('mouseup', onMouseUp)
    map.on('mouseout', onMouseOut)
    window.addEventListener('mouseup', onWindowMouseUp)
    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('keyup', onKeyUp)
    setCursor()
  }

  function detach(map: MapLibreMap): void {
    cancel()
    map.off('mousedown', onMouseDown)
    map.off('mousemove', onMouseMove)
    map.off('mouseup', onMouseUp)
    map.off('mouseout', onMouseOut)
    window.removeEventListener('mouseup', onWindowMouseUp)
    window.removeEventListener('keydown', onKeyDown)
    window.removeEventListener('keyup', onKeyUp)
    paused = false
    map.getCanvas().style.cursor = ''
  }

  return { shape, attach, detach }
}
