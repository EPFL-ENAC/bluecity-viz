/**
 * The pointer of the municipalities mode of the area picker: the commune
 * borders on the map, a click adds a commune, a second click takes it out.
 * The brush paints many communes in one stroke, Alt held takes them out.
 *
 * The communes are a vector source on the main map, under the names. The
 * hover and the selection ride feature-state on the BFS number, which is the
 * feature id of the tiles, so a click never touches a filter.
 */
import type { PickMode } from '@/composables/useCirclePick'
import {
  COMMUNES_HIT_LAYER,
  COMMUNES_SOURCE,
  COMMUNES_SOURCE_LAYER,
  communeLayerIds,
  communeLayers,
  swissCommunesSource,
  type CommuneColors
} from '@/config/toolLayers'
import { useScenarioStore } from '@/stores/scenario'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { BEFORE_LAYER } from '@/utils/bluecityGraph'
import type { Pt } from '@/utils/geometry'
import { municipalityLabel, type CommuneIndex } from '@/utils/municipalities'
import type { Map as MapLibreMap, MapMouseEvent, MapSourceDataEvent } from 'maplibre-gl'
import { shallowRef, watch, type ComputedRef, type Ref, type ShallowRef } from 'vue'

/** What the brush draws over the map, in pixels. `erase` when Alt is held. */
export interface CommuneBrush {
  at: Pt
  radius: number
  trail: Pt[]
  erase: boolean
}

export interface MunicipalityPick extends PickMode {
  /** null when the brush is not on the map. */
  brush: ShallowRef<CommuneBrush | null>
}

const MIN_BRUSH = 8
const MAX_BRUSH = 80

/** Typing in a field is not a shortcut. */
function isTyping(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null
  if (!el || !el.tagName) return false
  const tag = el.tagName.toLowerCase()
  return tag === 'input' || tag === 'textarea' || tag === 'select' || el.isContentEditable
}

/** The BFS number of a rendered commune, from its id. */
function bfsOf(feature: { id?: string | number }): number | null {
  const id = Number(feature.id)
  return Number.isInteger(id) && id > 0 ? id : null
}

export function useMunicipalityPick(options: {
  colors: ComputedRef<CommuneColors>
  canUse: ComputedRef<boolean>
  communes: Ref<CommuneIndex | null>
  invalidate: () => void
  checkNow: () => void
}): MunicipalityPick {
  const { colors, canUse, communes, invalidate, checkNow } = options
  const trafficStore = useTrafficAnalysisStore()
  const scenarioStore = useScenarioStore()

  let attached: MapLibreMap | null = null
  let waiting: MapLibreMap | null = null
  let hovered: number | null = null
  // The ids that carry the selected state on the map, to clear the ones taken out.
  let shown = new Set<number>()

  const brush = shallowRef<CommuneBrush | null>(null)
  /** Space held: the map pans instead of the brush painting. */
  let paused = false
  let stroke: { erase: boolean; trail: Pt[] } | null = null
  let frame = 0
  let pending: Pt | null = null

  function brushing(): boolean {
    return trafficStore.pickTool === 'brush'
  }

  function picked(): number[] {
    const draft = trafficStore.draftArea
    return draft?.kind === 'municipalities' ? draft.ofsIds : []
  }

  function state(current: MapLibreMap, id: number, value: Record<string, boolean>): void {
    current.setFeatureState(
      { source: COMMUNES_SOURCE, sourceLayer: COMMUNES_SOURCE_LAYER, id },
      value
    )
  }

  /** Write the selection and its colour as feature-state. */
  function paint(): void {
    const current = attached
    if (!current || !current.getSource(COMMUNES_SOURCE)) return
    const ids = new Set(picked())
    const ok = canUse.value
    try {
      for (const id of shown) {
        if (!ids.has(id)) state(current, id, { selected: false })
      }
      for (const id of ids) state(current, id, { selected: true, ok })
      shown = ids
    } catch {
      // the source is there but not parsed yet, the next sourcedata paints
    }
  }

  /**
   * Add the source and the layers. MapLibre refuses them until the style JSON
   * is parsed, and it has no flag for that, so try and retry on the next event.
   */
  function mount(): void {
    const current = attached
    if (!current) return
    try {
      if (!current.getSource(COMMUNES_SOURCE)) {
        current.addSource(COMMUNES_SOURCE, swissCommunesSource)
      }
      // Under the names, so they stay readable over the borders.
      const under = current.getLayer(BEFORE_LAYER) ? BEFORE_LAYER : undefined
      for (const layer of communeLayers(colors.value)) {
        if (current.getLayer(layer.id)) current.removeLayer(layer.id)
        current.addLayer(layer, under)
      }
    } catch {
      retryLater(current)
      return
    }
    // a new style starts with no state at all
    shown = new Set()
    hovered = null
    paint()
  }

  function retryLater(current: MapLibreMap): void {
    if (waiting === current) return
    waiting = current
    const again = () => {
      current.off('style.load', again)
      current.off('idle', again)
      waiting = null
      mount()
    }
    current.on('style.load', again)
    current.on('idle', again)
  }

  function unmount(current: MapLibreMap): void {
    for (const id of communeLayerIds()) {
      if (current.getLayer(id)) current.removeLayer(id)
    }
    if (current.getSource(COMMUNES_SOURCE)) current.removeSource(COMMUNES_SOURCE)
    shown = new Set()
    hovered = null
  }

  function communeAt(current: MapLibreMap, event: MapMouseEvent): number | null {
    if (!current.getLayer(COMMUNES_HIT_LAYER)) return null
    const [feature] = current.queryRenderedFeatures(event.point, { layers: [COMMUNES_HIT_LAYER] })
    return feature ? bfsOf(feature) : null
  }

  function setHover(current: MapLibreMap, id: number | null): void {
    if (id === hovered) return
    try {
      if (hovered !== null) state(current, hovered, { hover: false })
      if (id !== null) state(current, id, { hover: true })
    } catch {
      return
    }
    hovered = id
    setCursor()
  }

  function setCursor(): void {
    const current = attached
    if (!current) return
    let cursor = hovered !== null ? 'pointer' : ''
    // The brush draws its own circle, the arrow would sit on top of it.
    if (brushing()) cursor = paused ? 'grab' : 'none'
    current.getCanvas().style.cursor = cursor
  }

  /**
   * The communes under the brush as it slides from `from` to `to`.
   *
   * A rendered feature has no shape in pixels, so the query is a square inside
   * the circle, repeated every half radius along the way. It never takes a
   * commune the circle does not touch.
   */
  function communesAlong(current: MapLibreMap, from: Pt, to: Pt): number[] {
    if (!current.getLayer(COMMUNES_HIT_LAYER)) return []
    const radius = scenarioStore.brushRadius
    const half = radius / Math.SQRT2
    const length = Math.hypot(to[0] - from[0], to[1] - from[1])
    const steps = Math.max(1, Math.ceil(length / (radius / 2)))
    const ids = new Set<number>()
    for (let step = 0; step <= steps; step++) {
      const x = from[0] + ((to[0] - from[0]) * step) / steps
      const y = from[1] + ((to[1] - from[1]) * step) / steps
      const box: [Pt, Pt] = [
        [x - half, y - half],
        [x + half, y + half]
      ]
      for (const feature of current.queryRenderedFeatures(box, { layers: [COMMUNES_HIT_LAYER] })) {
        const id = bfsOf(feature)
        if (id !== null) ids.add(id)
      }
    }
    return [...ids]
  }

  function paintStroke(current: MapLibreMap, from: Pt, to: Pt): void {
    if (!stroke) return
    const ids = communesAlong(current, from, to)
    if (ids.length === 0) return
    if (stroke.erase) trafficStore.removeDraftMunicipalities(ids)
    else trafficStore.addDraftMunicipalities(ids)
  }

  function showBrush(at: Pt | null): void {
    brush.value =
      at && brushing() && !paused
        ? {
            at,
            radius: scenarioStore.brushRadius,
            trail: stroke ? [...stroke.trail] : [],
            erase: stroke?.erase ?? false
          }
        : null
  }

  function onMouseDown(event: MapMouseEvent): void {
    const current = attached
    if (!current || !brushing() || paused) return
    // The map must not pan under the stroke.
    event.preventDefault()
    current.dragPan.disable()
    const at: Pt = [event.point.x, event.point.y]
    stroke = { erase: event.originalEvent.altKey, trail: [at] }
    paintStroke(current, at, at)
    showBrush(at)
  }

  function onMouseMove(event: MapMouseEvent): void {
    const current = attached
    if (!current) return
    if (!brushing()) {
      setHover(current, communeAt(current, event))
      return
    }
    if (paused) return
    pending = [event.point.x, event.point.y]
    if (frame) return
    frame = requestAnimationFrame(() => {
      frame = 0
      const at = pending
      if (!attached || !at) return
      if (stroke) {
        const from = stroke.trail[stroke.trail.length - 1] ?? at
        stroke.trail.push(at)
        paintStroke(attached, from, at)
      }
      showBrush(at)
    })
  }

  /** End the stroke. `at` is null when the button went up off the map. */
  function stopStroke(at: Pt | null): void {
    if (!stroke) return
    if (frame) {
      cancelAnimationFrame(frame)
      frame = 0
    }
    const current = attached
    if (current) {
      // The last move may not have had its frame yet, so take that sample now.
      if (at) paintStroke(current, stroke.trail[stroke.trail.length - 1] ?? at, at)
      current.dragPan.enable()
    }
    const end = at ?? stroke.trail[stroke.trail.length - 1] ?? null
    stroke = null
    showBrush(at ? end : null)
  }

  /** Drop the stroke and the circle, nothing more is painted. */
  function cancelStroke(): void {
    if (frame) {
      cancelAnimationFrame(frame)
      frame = 0
    }
    pending = null
    if (stroke) {
      stroke = null
      attached?.dragPan.enable()
    }
    brush.value = null
  }

  function onMouseUp(event: MapMouseEvent): void {
    stopStroke([event.point.x, event.point.y])
  }

  function onWindowMouseUp(): void {
    stopStroke(null)
  }

  function onMouseOut(): void {
    const current = attached
    if (current) setHover(current, null)
    if (!stroke) brush.value = null
  }

  function onClick(event: MapMouseEvent): void {
    const current = attached
    // The brush already painted on the way down.
    if (!current || brushing()) return
    const id = communeAt(current, event)
    if (id !== null) trafficStore.toggleDraftMunicipality(id)
  }

  /**
   * B switches the tool, [ and ] resize the brush, and Space held pans the
   * map without leaving the brush, like the street brush of the workbench.
   */
  function onKeyDown(event: KeyboardEvent): void {
    if (!attached || isTyping(event.target)) return
    if (event.metaKey || event.ctrlKey || event.altKey) return
    if (event.code === 'Space') {
      if (!brushing() || paused) return
      // Space on a focused button would press it.
      event.preventDefault()
      paused = true
      if (!stroke) brush.value = null
      setCursor()
      return
    }
    const key = event.key.toLowerCase()
    if (key === 'b') {
      trafficStore.pickTool = brushing() ? 'pointer' : 'brush'
    } else if (brushing() && (key === '[' || key === ']')) {
      const step = key === '[' ? -4 : 4
      scenarioStore.brushRadius = Math.max(
        MIN_BRUSH,
        Math.min(MAX_BRUSH, scenarioStore.brushRadius + step)
      )
      const at = brush.value?.at ?? null
      if (at) showBrush(at)
    }
  }

  function onKeyUp(event: KeyboardEvent): void {
    if (event.code !== 'Space' || !paused) return
    paused = false
    setCursor()
  }

  function onSourceData(event: MapSourceDataEvent): void {
    // Tiles arrive after the click that picked them, paint them once loaded.
    if (event.sourceId === COMMUNES_SOURCE && event.isSourceLoaded) paint()
  }

  // A click, a Remove in the dock, or a new answer: the map follows.
  watch([() => picked().join(','), canUse], paint)

  // A click or a Remove in the dock: the old answer is stale, ask again.
  watch(
    () => picked().join(','),
    (ids, previous) => {
      if (!attached || ids === previous) return
      invalidate()
      checkNow()
    }
  )

  // The name of the selection, from the local index. Nothing without it: the
  // dock then counts the communes.
  watch([() => picked().join(','), communes], () => {
    if (!attached) return
    const ids = picked()
    const index = communes.value
    trafficStore.setDraftName(ids.length && index ? municipalityLabel(ids, index) : null)
  })

  watch(colors, () => {
    if (attached) mount()
  })

  // A new tool: no stroke half done, no hover left from the pointer.
  watch(
    () => trafficStore.pickTool,
    () => {
      const current = attached
      if (!current) return
      cancelStroke()
      setHover(current, null)
      setCursor()
    }
  )

  function attach(current: MapLibreMap): void {
    if (attached) return
    attached = current
    current.on('mousedown', onMouseDown)
    current.on('mousemove', onMouseMove)
    current.on('mouseup', onMouseUp)
    current.on('mouseout', onMouseOut)
    current.on('click', onClick)
    window.addEventListener('mouseup', onWindowMouseUp)
    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('keyup', onKeyUp)
    current.on('style.load', mount)
    current.on('sourcedata', onSourceData)
    mount()
    setCursor()
    const ids = picked()
    const index = communes.value
    if (ids.length && index) trafficStore.setDraftName(municipalityLabel(ids, index))
  }

  function detach(current: MapLibreMap): void {
    if (!attached) return
    cancelStroke()
    attached = null
    paused = false
    current.off('mousedown', onMouseDown)
    current.off('mousemove', onMouseMove)
    current.off('mouseup', onMouseUp)
    current.off('mouseout', onMouseOut)
    current.off('click', onClick)
    window.removeEventListener('mouseup', onWindowMouseUp)
    window.removeEventListener('keydown', onKeyDown)
    window.removeEventListener('keyup', onKeyUp)
    current.off('style.load', mount)
    current.off('sourcedata', onSourceData)
    current.dragPan.enable()
    current.getCanvas().style.cursor = ''
    unmount(current)
  }

  return { attach, detach, brush }
}
