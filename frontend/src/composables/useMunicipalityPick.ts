/**
 * The pointer of the municipalities mode of the area picker: the commune
 * borders on the map, a click adds a commune, a second click takes it out.
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
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { BEFORE_LAYER } from '@/utils/bluecityGraph'
import { municipalityLabel, type CommuneIndex } from '@/utils/municipalities'
import type { Map as MapLibreMap, MapMouseEvent, MapSourceDataEvent } from 'maplibre-gl'
import { watch, type ComputedRef, type Ref } from 'vue'

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
}): PickMode {
  const { colors, canUse, communes, invalidate, checkNow } = options
  const trafficStore = useTrafficAnalysisStore()

  let attached: MapLibreMap | null = null
  let waiting: MapLibreMap | null = null
  let hovered: number | null = null
  // The ids that carry the selected state on the map, to clear the ones taken out.
  let shown = new Set<number>()

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
    current.getCanvas().style.cursor = id !== null ? 'pointer' : ''
  }

  function onMouseMove(event: MapMouseEvent): void {
    const current = attached
    if (current) setHover(current, communeAt(current, event))
  }

  function onMouseOut(): void {
    const current = attached
    if (current) setHover(current, null)
  }

  function onClick(event: MapMouseEvent): void {
    const current = attached
    if (!current) return
    const id = communeAt(current, event)
    if (id !== null) trafficStore.toggleDraftMunicipality(id)
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

  function attach(current: MapLibreMap): void {
    if (attached) return
    attached = current
    current.on('mousemove', onMouseMove)
    current.on('mouseout', onMouseOut)
    current.on('click', onClick)
    current.on('style.load', mount)
    current.on('sourcedata', onSourceData)
    mount()
    const ids = picked()
    const index = communes.value
    if (ids.length && index) trafficStore.setDraftName(municipalityLabel(ids, index))
  }

  function detach(current: MapLibreMap): void {
    if (!attached) return
    attached = null
    current.off('mousemove', onMouseMove)
    current.off('mouseout', onMouseOut)
    current.off('click', onClick)
    current.off('style.load', mount)
    current.off('sourcedata', onSourceData)
    current.getCanvas().style.cursor = ''
    unmount(current)
  }

  return { attach, detach }
}
