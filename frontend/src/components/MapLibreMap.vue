<script setup lang="ts">
import LoadingBar from '@/components/LoadingBar.vue'
import { useMapEvents } from '@/composables/useMapEvents'
import type { CustomSourceSpecification, MapLayerConfig } from '@/config/layerTypes'
import { mapConfig } from '@/config/mapConfig'
import {
  theme as basemapTheme,
  buildStyle,
  clearPatterns,
  loadTiles,
  setMapTheme,
  wirePatterns,
  type BasemapTheme
} from '@/utils/epflBasemap'
import 'maplibre-gl/dist/maplibre-gl.css'

import type { LegendColor } from '@/utils/legendColor'
import {
  addProtocol,
  AttributionControl,
  Map as MapLibre,
  NavigationControl,
  ScaleControl,
  VectorTileSource,
  type AddLayerObject,
  type FilterSpecification,
  type LngLatLike,
  type SourceSpecification,
  type StyleSetterOptions,
  type StyleSpecification,
  type TransformStyleFunction
} from 'maplibre-gl'
import { markRaw, onMounted, ref, shallowRef, watch, type Ref } from 'vue'

import { useApiKeyStore } from '@/stores/apiKey'
import { useLayersStore } from '@/stores/layers'
import { useThemeStore } from '@/stores/theme'
import { Protocol } from 'pmtiles'

const apiKeyStore = useApiKeyStore()
const layersStore = useLayersStore()
const themeStore = useThemeStore()

const props = withDefaults(
  defineProps<{
    center?: LngLatLike
    zoom?: number
    aspectRatio?: number
    minZoom?: number
    maxZoom?: number
    filterIds?: string[]
    popupLayerIds?: string[]
    areaLayerIds?: string[]
    idxImage?: number
    variableSelected?: string
    legendColors?: LegendColor[]
    callbackLoaded?: () => void
  }>(),
  {
    center: undefined,
    zoom: 12,
    idxImage: 0,
    variableSelected: 't2',
    aspectRatio: undefined,
    minZoom: undefined,
    maxZoom: undefined,
    filterIds: undefined,
    legendColors: undefined,
    callbackLoaded: undefined,
    popupLayerIds: () => [],
    areaLayerIds: () => []
  }
)

const loading = ref(true)
const container = ref<HTMLDivElement | null>(null)
// Shallow on purpose: Vue must not walk or proxy the MapLibre instance.
const map = shallowRef<MapLibre | undefined>(undefined)
const hasLoaded = ref(false)
const protocol = new Protocol()

// Dataset layers are added to the map the first time they are shown, so a
// fresh load only fetches the tiles of the selected layers.
const layerIndex = new Map<string, MapLayerConfig>(
  mapConfig.layers.map((entry) => [entry.layer.id, entry])
)
// Config order is the z-order, we keep it whatever the activation order is.
const orderedLayerIds = mapConfig.layers.map((entry) => entry.layer.id)
const layerOrder = new Map<string, number>(orderedLayerIds.map((id, index) => [id, index]))

// Set when MapLibre refuses an addLayer because a style is still loading.
let needsResync = false

// One cancellable timer for the loading bar, never a polling loop.
const LOADING_BAR_DELAY = 150
let loadingTimer: number | undefined

// Ink-on-paper themes of the Substrat basemap. Both are the same engine and
// the same layers, only the colours change.
const SUBSTRAT_THEMES: Record<string, BasemapTheme> = {
  substrat: basemapTheme({ ink: '#141414', paper: '#ffffff', density: 0.8 }),
  'substrat-dark': basemapTheme({ ink: '#F2F2F2', paper: '#141414', density: 0.8 })
}

function isSubstratKey(key: string): boolean {
  return key.startsWith('substrat')
}

function themeFor(key: string): BasemapTheme {
  return SUBSTRAT_THEMES[key] ?? SUBSTRAT_THEMES.substrat
}

/** Either a style URL (public/style/*.json) or a style built by the EPFL engine. */
function styleFor(key: string): string | StyleSpecification {
  return isSubstratKey(key) ? buildStyle('substrat', themeFor(key)) : key
}

// Use the map events composable
const mapEventManager = useMapEvents(map as Ref<MapLibre | undefined>)

addProtocol('pmtiles', protocol.tile)

/** Our own fields are not part of the MapLibre source spec. */
function stripSource(source: CustomSourceSpecification): SourceSpecification {
  const spec = { ...source } as Record<string, unknown>
  delete spec.id
  delete spec.label
  return spec as unknown as SourceSpecification
}

/** Keep the config z-order: insert before the next layer already on the map. */
function beforeIdFor(layerId: string): string | undefined {
  const index = layerOrder.get(layerId)
  if (index === undefined) return undefined
  for (let i = index + 1; i < orderedLayerIds.length; i++) {
    if (map.value?.getLayer(orderedLayerIds[i])) return orderedLayerIds[i]
  }
  return undefined
}

/**
 * Add the source and the layer of one dataset entry, hidden, if they are not
 * on the map yet. Several layers can share one source, it is added once.
 */
function ensureLayer(entry: MapLayerConfig): boolean {
  const mapInstance = map.value
  if (!mapInstance) return false

  try {
    if (!mapInstance.getSource(entry.source.id)) {
      mapInstance.addSource(entry.source.id, stripSource(entry.source))
    }
    if (!mapInstance.getLayer(entry.layer.id)) {
      const spec = {
        ...entry.layer,
        source: entry.source.id,
        layout: { ...entry.layer.layout, visibility: 'none' }
      } as AddLayerObject
      mapInstance.addLayer(spec, beforeIdFor(entry.layer.id))
      applyCategoryFilter(entry.layer.id)
    }
    return true
  } catch {
    // The style is still loading. Redo the whole sync once it is done.
    needsResync = true
    return false
  }
}

// onMounted and the api key watcher can both call initMap. The tile fetch in
// between is async, so a plain `if (map.value)` guard is not enough: a second
// call would slip through and build a second map in the same container.
let initStarted = false

async function initMap() {
  if (map.value || initStarted) return
  initStarted = true

  // The Trait style needs the OpenFreeMap tile URLs (memoised fetch), so build
  // the style only after they arrived.
  try {
    await loadTiles()
  } catch (error) {
    initStarted = false
    throw error
  }

  const initialStyle = styleFor(themeStore.theme)

  const newMap = new MapLibre({
    container: container.value as HTMLDivElement,
    style: initialStyle,
    center: props.center,
    zoom: props.zoom,
    minZoom: props.minZoom,
    maxZoom: props.maxZoom,
    attributionControl: false,
    transformRequest: function (url, resourceType) {
      const apiKey = apiKeyStore.apiKey

      if (resourceType === 'Tile' && url.includes('pmtiles://')) {
        return {
          url: url + '?apikey=' + apiKey,
          credentials: 'include'
        }
      }

      if (url.includes('/bluecity/')) {
        return {
          url: url + '?apikey=' + apiKey,
          credentials: 'include'
        }
      }

      return { url: url }
    }
  })

  map.value = markRaw(newMap)

  // Trait textures are drawn on demand, once per map.
  setMapTheme(newMap, themeFor(themeStore.theme))
  wirePatterns(newMap)

  newMap.addControl(new NavigationControl({ showCompass: false }), 'top-right')
  newMap.addControl(new ScaleControl({ maxWidth: 110, unit: 'metric' }), 'bottom-left')
  newMap.addControl(new AttributionControl({ compact: true }), 'bottom-right')

  // Loading bar. 'dataloading' fires per tile, so wait a bit before showing
  // the bar, and 'idle' fires once the map has nothing left to load.
  newMap.on('dataloading', () => {
    if (loadingTimer !== undefined) return
    loadingTimer = window.setTimeout(() => {
      loadingTimer = undefined
      loading.value = true
    }, LOADING_BAR_DELAY)
  })

  newMap.on('idle', () => {
    if (loadingTimer !== undefined) {
      window.clearTimeout(loadingTimer)
      loadingTimer = undefined
    }
    loading.value = false
  })

  newMap.on('load', () => {
    if (!map.value) return
    hasLoaded.value = true
    loading.value = false
    map.value.resize()

    // The selected layers are added here, by the parent sync.
    if (props.callbackLoaded) {
      props.callbackLoaded()
    }
  })

  // A layer asked for while a style was loading is added on the next style event.
  newMap.on('styledata', () => {
    if (!needsResync || !hasLoaded.value) return
    needsResync = false
    if (props.callbackLoaded) props.callbackLoaded()
  })
}

onMounted(() => {
  if (apiKeyStore.apiKey) {
    initMap()
  }
})

watch(
  () => apiKeyStore.apiKey,
  () => {
    initMap()
  }
)

const setFilter = (
  layerId: string,
  filter?: FilterSpecification | null | undefined,
  options?: StyleSetterOptions | undefined
) => {
  map.value?.setFilter(layerId, filter, options)
}

const getFilter = (layerId: string) => {
  return map.value?.getFilter(layerId)
}

const setPaintProperty = (
  layerId: string,
  name: string,
  value: any,
  options?: StyleSetterOptions | undefined
) => {
  map.value?.setPaintProperty(layerId, name, value, options)
}

const queryFeatures = (filter: any[]) => {
  return map.value?.querySourceFeatures('trajectories', {
    sourceLayer: 'trajectories',
    filter: filter as FilterSpecification,
    validate: false
  })
}

const queryRenderedFeatures = () => {
  return map.value?.queryRenderedFeatures()
}

const onZoom = (callback: () => void) => {
  map.value?.on('zoom', callback)
}

const changeSourceTilesUrl = (sourceId: string, url: string) => {
  const source = map.value?.getSource(sourceId) as VectorTileSource
  source.setUrl(url)
}

const getSourceTilesUrl = (sourceId: string) => {
  const source = map.value?.getSource(sourceId) as VectorTileSource
  if (source && source.url) return source.url
  else return ''
}

/**
 * Show or hide one dataset layer, adding it to the map on first use.
 * Returns whether the map is in the asked state now.
 */
const setLayerVisibility = (layerId: string, visibility: boolean): boolean => {
  const mapInstance = map.value
  if (!mapInstance || !hasLoaded.value) return false

  const entry = layerIndex.get(layerId)
  if (!entry) return false

  if (visibility) {
    if (!ensureLayer(entry)) return false
    if (mapInstance.getLayoutProperty(layerId, 'visibility') !== 'visible') {
      mapInstance.setLayoutProperty(layerId, 'visibility', 'visible')
    }
    mapEventManager.attachPopupListeners(layerId, entry.label ?? '')
    return true
  }

  // Nothing to hide when the layer was never added.
  if (!mapInstance.getLayer(layerId)) return true

  mapEventManager.detachPopupListeners(layerId)
  if (mapInstance.getLayoutProperty(layerId, 'visibility') !== 'none') {
    mapInstance.setLayoutProperty(layerId, 'visibility', 'none')
  }
  return true
}

const getPaintProperty = (layerId: string, name: string) => {
  if (hasLoaded.value) return map.value?.getPaintProperty(layerId, name)
}

/** Hide the categories the user unchecked in the legend. */
function buildCategoryFilter(
  variablesRecord: Record<string, string[]>
): FilterSpecification | null {
  let filter: FilterSpecification | null = null
  for (const [variable, categories] of Object.entries(variablesRecord)) {
    const categoriesListToFilter = [...categories]
    filter =
      categoriesListToFilter.length > 0
        ? ([
            '!',
            ['in', ['get', variable], ['literal', categoriesListToFilter]]
          ] as FilterSpecification)
        : null
  }
  return filter
}

function applyCategoryFilter(layerId: string) {
  const mapInstance = map.value
  if (!mapInstance?.getLayer(layerId)) return
  const variablesRecord = layersStore.filteredCategories[layerId]
  if (!variablesRecord) return
  mapInstance.setFilter(layerId, buildCategoryFilter(variablesRecord))
}

// Filter categorical layers by categories
watch(
  () => layersStore.filteredCategories,
  (filteredCategories) => {
    Object.keys(filteredCategories).forEach((layerId) => applyCategoryFilter(layerId))
  },
  { deep: true }
)

// Automatic pitch change when 3D layers are added or removed
watch(
  () => layersStore.visibleLayers,
  (visibleLayers, oldVisibleLayers) => {
    const oldThreeDimLayers = oldVisibleLayers.filter(
      (layer) => layer.layer.type === 'fill-extrusion'
    )
    const threeDimLayers = visibleLayers.filter((layer) => layer.layer.type === 'fill-extrusion')
    const had3DLayer = oldThreeDimLayers.length > 0
    const has3DLayer = threeDimLayers.length > 0

    if (!had3DLayer && has3DLayer) {
      if (map.value?.getPitch() === 0)
        map.value?.easeTo({ pitch: 40, center: map.value?.getCenter() })
    } else if (had3DLayer && !has3DLayer) {
      map.value?.easeTo({ pitch: 0, center: map.value?.getCenter() })
    }
  }
)

defineExpose({
  map,
  getPaintProperty,
  setFilter,
  getFilter,
  queryFeatures,
  queryRenderedFeatures,
  setPaintProperty,
  onZoom,
  changeSourceTilesUrl,
  setLayerVisibility,
  getSourceTilesUrl
})

/**
 * Copy the colours of one Trait theme onto the other. Same layers, same ids,
 * so only the paint (and layout) values that really differ are written.
 */
function applyPaintDiff(
  mapInstance: MapLibre,
  previous: StyleSpecification,
  next: StyleSpecification
) {
  const previousById = new Map(previous.layers.map((layer) => [layer.id, layer]))

  for (const layer of next.layers) {
    if (!mapInstance.getLayer(layer.id)) continue
    const before = previousById.get(layer.id)

    /* eslint-disable @typescript-eslint/no-explicit-any */
    const paint = ((layer as any).paint ?? {}) as Record<string, unknown>
    const beforePaint = ((before as any)?.paint ?? {}) as Record<string, unknown>
    for (const key of Object.keys({ ...beforePaint, ...paint })) {
      if (JSON.stringify(paint[key]) !== JSON.stringify(beforePaint[key])) {
        mapInstance.setPaintProperty(layer.id, key, paint[key])
      }
    }

    const layout = ((layer as any).layout ?? {}) as Record<string, unknown>
    const beforeLayout = ((before as any)?.layout ?? {}) as Record<string, unknown>
    /* eslint-enable @typescript-eslint/no-explicit-any */
    for (const key of Object.keys({ ...beforeLayout, ...layout })) {
      if (JSON.stringify(layout[key]) !== JSON.stringify(beforeLayout[key])) {
        mapInstance.setLayoutProperty(layer.id, key, layout[key])
      }
    }
  }
}

const configSourceIds = new Set(mapConfig.sources.map((source) => source.id))

/**
 * setStyle drops everything the new style does not declare. Put our own
 * dataset sources and layers back, with the filter and the visibility they
 * had. Layers of other plugins (Deck.gl) are left alone, they re-add theirs.
 *
 * The graph overlay sources (bc-*) are carried too, with the same `data`
 * object, so the 6 MB of edges are not fetched and tiled again. Its layers are
 * not: useGraphOverlay re-adds them on style.load, under the street labels of
 * the new style.
 */
const carryOverlay: TransformStyleFunction = (previous, next) => {
  if (!previous) return next

  const sources = { ...next.sources }
  for (const [id, source] of Object.entries(previous.sources)) {
    const keep = configSourceIds.has(id) || id.startsWith('bc-')
    if (keep && !sources[id]) sources[id] = source
  }

  return {
    ...next,
    sources,
    layers: [...next.layers, ...previous.layers.filter((layer) => layerIndex.has(layer.id))]
  }
}

watch(
  () => themeStore.theme,
  (next, previous) => {
    const mapInstance = map.value
    if (!mapInstance) return

    // Drop the generated textures so they are redrawn with the new ink colour.
    setMapTheme(mapInstance, themeFor(next))
    clearPatterns(mapInstance)

    // Substrat light to Substrat dark: same style, other colours. No setStyle,
    // so the dataset layers and their tiles are never touched.
    if (isSubstratKey(next) && isSubstratKey(previous)) {
      applyPaintDiff(
        mapInstance,
        buildStyle('substrat', themeFor(previous)),
        buildStyle('substrat', themeFor(next))
      )
      return
    }

    mapInstance.setStyle(styleFor(next), { diff: true, transformStyle: carryOverlay })
  }
)
</script>

<template>
  <div class="map-wrapper">
    <LoadingBar :loading="loading" />
    <div ref="container" class="map" />
    <slot name="legend"></slot>
  </div>
</template>

<style scoped>
.map-wrapper {
  position: absolute;
  inset: 0;
}

.map {
  height: 100%;
  width: 100%;
  position: relative;
}
</style>

<style>
/* Global styles for the popup (not scoped) */
.feature-popup .maplibregl-popup-content {
  background: var(--bc-panel);
  color: var(--bc-ink);
  padding: 10px 12px;
  font-family: var(--bc-font-sans);
  overflow-y: auto;
  max-height: 500px;
}

.popup-table {
  border-collapse: collapse;
  width: 100%;
}

.popup-content > h3 {
  margin-bottom: 1rem;
}

.popup-table tr:nth-child(even) {
  background-color: rgba(0, 0, 0, 0.05);
}

.popup-table td {
  padding: 4px 6px;
  font-size: small;
}

.property-name {
  font-family: var(--bc-font-mono);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--bc-grey);
  white-space: nowrap;
  font-size: var(--bc-fs-micro);
}

.property-value {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
