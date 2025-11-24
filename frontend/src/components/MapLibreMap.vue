<script setup lang="ts">
import 'maplibre-gl/dist/maplibre-gl.css'
import LoadingCircle from '@/components/LoadingCircle.vue'
import { mapConfig } from '@/config/mapConfig'
import { useMapEvents } from '@/composables/useMapEvents'

import {
  FullscreenControl,
  Map,
  NavigationControl,
  ScaleControl,
  VectorTileSource,
  type FilterSpecification,
  type LngLatLike,
  type StyleSetterOptions,
  addProtocol
} from 'maplibre-gl'
import type { LegendColor } from '@/utils/legendColor'
import { computed, onMounted, ref, watch, type Ref } from 'vue'

import { Protocol } from 'pmtiles'
import { useApiKeyStore } from '@/stores/apiKey'
import { useLayersStore } from '@/stores/layers'
import { useThemeStore } from '@/stores/theme'

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
const map = ref<any | undefined>(undefined)
const hasLoaded = ref(false)
const protocol = new Protocol()

const styleSpec = computed(() => {
  return themeStore.theme
})

// Use the map events composable
const mapEventManager = useMapEvents(map as Ref<Map | undefined>)

addProtocol('pmtiles', protocol.tile)

function initMap() {
  const newMap = new Map({
    container: container.value as HTMLDivElement,
    style: styleSpec.value,
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
  }) as Map

  map.value = newMap

  const mapInstance = map.value as Map

  // map.showTileBoundaries = true
  mapInstance.addControl(new NavigationControl({}))
  mapInstance.addControl(new ScaleControl({}))
  mapInstance.addControl(
    new FullscreenControl({
      container: document.getElementById('map-time-input-container') ?? undefined
    })
  )

  mapInstance.on('load', () => {
    if (!map.value) return
    hasLoaded.value = true
    loading.value = false
    map.value.resize()

    // Add all sources dynamically
    Object.entries(mapConfig.layers).forEach(([, { id, source, layer }]) => {
      map.value?.addSource(id, source)
      map.value?.addLayer(layer)
    })

    function testTilesLoaded() {
      if (map.value?.areTilesLoaded()) {
        loading.value = false
      } else {
        loading.value = true
        setTimeout(testTilesLoaded, 1000)
      }
    }

    function handleDataEvent() {
      if (map.value?.areTilesLoaded()) {
        loading.value = false
      } else {
        testTilesLoaded()
      }
    }

    // Attach popup listeners to each layer using our composable
    // mapConfig.layers.forEach((layer) => attachPopupListeners(layer.layer.id, layer.label))

    mapInstance.on('sourcedata', handleDataEvent)
    mapInstance.on('sourcedataloading', handleDataEvent)

    // filterSP0Period(layersStore.sp0Period)

    if (props.callbackLoaded) {
      props.callbackLoaded()
    }
  })
}

onMounted(() => {
  addProtocol('pmtiles', protocol.tile)
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
const setLayerVisibility = (layerId: string, visibility: boolean) => {
  const layerLabel = mapConfig.layers.find((layer) => layer.layer.id === layerId)?.label
  if (visibility) mapEventManager.attachPopupListeners(layerId, layerLabel ?? '')
  else mapEventManager.detachPopupListeners(layerId)
  map.value?.setLayoutProperty(layerId, 'visibility', visibility ? 'visible' : 'none')
}

const getPaintProperty = (layerId: string, name: string) => {
  if (hasLoaded.value) return map.value?.getPaintProperty(layerId, name)
}

// Filter categorical layers by categories
watch(
  () => layersStore.filteredCategories,
  (filteredCategories) => {
    Object.entries(filteredCategories).forEach(([layerID, variablesRecord]) => {
      Object.entries(variablesRecord).forEach(([variable, categories]) => {
        const categoriesListToFilter = [...categories]

        if (categoriesListToFilter.length > 0) {
          const filter = [
            '!',
            ['in', ['get', variable], ['literal', categoriesListToFilter]]
          ] as FilterSpecification
          setFilter(layerID, filter)
        } else if (categoriesListToFilter.length == 0) {
          setFilter(layerID, null)
        }
      })
    })
  },
  { deep: true }
)

// function filterSP0Period(period: string) {
//   const sp0Group = layersStore.layerGroups.find((group) => group.id === 'sp0_migration')

//   if (!sp0Group) return
//   sp0Group.layers
//     .filter((layer) => {
//       return layersStore.selectedLayers.includes(layer.layer.id)
//     })
//     .forEach((layer) => {
//       const filter = ['==', ['get', 'year'], period] as FilterSpecification
//       map.value?.setFilter(layer.layer.id, filter)
//     })
// }

// // Filter SP0 migration layers by period
// watch(
//   () => [layersStore.sp0Period, layersStore.selectedLayers],
//   ([newPeriod]) => filterSP0Period(newPeriod as string),
//   { immediate: true }
// )

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

watch(
  () => styleSpec.value,
  (styleSpec) => {
    if (!map.value) return

    // Store current layers state before style change
    const currentLayersVisibility = mapConfig.layers.map(({ layer }) => ({
      id: layer.id,
      visible: map.value?.getLayoutProperty(layer.id, 'visibility') !== 'none'
    }))

    // Set the new style
    map.value.setStyle(styleSpec)

    // Re-add sources and layers after style loads
    map.value.once('styledata', () => {
      if (!map.value) return

      // Re-add all sources and layers
      Object.entries(mapConfig.layers).forEach(([, { id, source, layer }]) => {
        map.value?.addSource(id, source)
        map.value?.addLayer(layer)
      })

      // Restore layer visibility
      currentLayersVisibility.forEach(({ id, visible }) => {
        setLayerVisibility(id, visible)
      })
    })
  },
  { immediate: true }
)
</script>

<template>
  <v-container class="pa-0 position-relative fill-height" fluid>
    <div ref="container" class="map fill-height">
      <loading-circle :loading="loading" />
    </div>
    <slot name="legend"></slot>
  </v-container>
</template>

<style scoped>
.map {
  height: 100%;
  width: 100%;
  position: relative;
}
</style>

<style>
/* Global styles for the popup (not scoped) */
.feature-popup .maplibregl-popup-content {
  background: rgba(255, 255, 255, 0.95);
  padding: 10px;
  font-family: inherit;
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
  font-weight: bold;
  text-transform: uppercase;
  color: rgba(0, 0, 0, 0.7);
  white-space: nowrap;
  font-size: smaller;
}

.property-value {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
