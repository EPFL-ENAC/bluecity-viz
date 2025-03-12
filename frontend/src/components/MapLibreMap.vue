<script setup lang="ts">
import 'maplibre-gl/dist/maplibre-gl.css'
import LoadingCircle from '@/components/LoadingCircle.vue'

import { mapConfig } from '@/config/mapConfig'

import {
  FullscreenControl,
  Map as Maplibre,
  NavigationControl,
  Popup,
  ScaleControl,
  VectorTileSource,
  type FilterSpecification,
  type LngLatLike,
  type StyleSetterOptions,
  type StyleSpecification,
  addProtocol
} from 'maplibre-gl'
import type { LegendColor } from '@/utils/legendColor'
import { onMounted, ref, watch } from 'vue'

import { Protocol } from 'pmtiles'
import { useApiKeyStore } from '@/stores/apiKey'

const apiKeyStore = useApiKeyStore()

const props = withDefaults(
  defineProps<{
    styleSpec: string | StyleSpecification
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
let map: Maplibre | undefined = undefined
const hasLoaded = ref(false)
const protocol = new Protocol()

addProtocol('pmtiles', protocol.tile)

function initMap() {
  map = new Maplibre({
    container: container.value as HTMLDivElement,
    style: props.styleSpec,
    center: props.center,
    zoom: props.zoom,
    minZoom: props.minZoom,
    pitch: 40,
    maxZoom: props.maxZoom,
    attributionControl: false,
    transformRequest: function (url, resourceType) {
      const apiKey = apiKeyStore.apiKey

      if (resourceType === 'Tile' && url.includes('pmtiles://')) {
        return {
          url: url + '?apikey=' + apiKey,
          // headers: { 'X-Api-Key': apiKey, Authorization: apiKey },
          credentials: 'include'
        }
      }

      if (url.includes('/bluecity/')) {
        return {
          url: url + '?apikey=' + apiKey,
          // headers: { 'X-Api-Key': apiKey, Authorization: apiKey },
          credentials: 'include'
        }
      }

      return { url: url }
    }
  })

  // map.showTileBoundaries = true
  map.addControl(new NavigationControl({}))
  map.addControl(new ScaleControl({}))
  map.addControl(
    new FullscreenControl({
      container: document.getElementById('map-time-input-container') ?? undefined
    })
  )
  map.on('load', () => {
    // filterLayers(props.filterIds)
    if (!map) return
    hasLoaded.value = true
    loading.value = false
    map.resize()

    // Add all sources dynamically
    Object.entries(mapConfig.layers).forEach(([, { id, source, layer }]) => {
      map?.addSource(id, source)
      map?.addLayer(layer)
    })

    function testTilesLoaded() {
      if (map?.areTilesLoaded()) {
        loading.value = false
      } else {
        loading.value = true
        setTimeout(testTilesLoaded, 1000)
      }
    }

    function handleDataEvent() {
      if (map?.areTilesLoaded()) {
        loading.value = false
      } else {
        testTilesLoaded()
      }
    }

    map.on('sourcedata', handleDataEvent)

    map.on('sourcedataloading', handleDataEvent)

    map.on('mouseleave', 'trajectories', () => {
      if (map) map.getCanvas().classList.remove('hovered-feature')
    })

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

let throttleTimer = new Map<string, boolean>()

const throttle = (callback: () => void, id: string, time: number) => {
  if (throttleTimer.get(id)) {
    // If currently throttled, exit the function
    return
  }
  // Set the throttle flag
  throttleTimer.set(id, true)
  // Clear the throttle flag after the specified time
  setTimeout(() => {
    throttleTimer.set(id, false)
  }, time)
  callback()
}

const setFilter = (
  layerId: string,
  filter?: FilterSpecification | null | undefined,
  options?: StyleSetterOptions | undefined
) => {
  if (hasLoaded.value) {
    throttle(() => map?.setFilter(layerId, filter, options), layerId + '-filter', 100)
  }
}

const setPaintProperty = (
  layerId: string,
  name: string,
  value: any,
  options?: StyleSetterOptions | undefined
) => {
  if (hasLoaded.value)
    throttle(() => map?.setPaintProperty(layerId, name, value, options), layerId + '-paint', 100)
}

const queryFeatures = (filter: any[]) => {
  return map?.querySourceFeatures('trajectories', {
    sourceLayer: 'trajectories',
    filter: filter as FilterSpecification,
    validate: false
  })
}

const queryRenderedFeatures = () => {
  return map?.queryRenderedFeatures()
}

const onZoom = (callback: () => void) => {
  map?.on('zoom', callback)
}

const changeSourceTilesUrl = (sourceId: string, url: string) => {
  const source = map?.getSource(sourceId) as VectorTileSource
  source.setUrl(url)
}

const getSourceTilesUrl = (sourceId: string) => {
  const source = map?.getSource(sourceId) as VectorTileSource
  if (source && source.url) return source.url
  else return ''
}
const setLayerVisibility = (layerId: string, visibility: boolean) => {
  map?.setLayoutProperty(layerId, 'visibility', visibility ? 'visible' : 'none')
}

const getPaintProperty = (layerId: string, name: string) => {
  if (hasLoaded.value) return map?.getPaintProperty(layerId, name)
}

defineExpose({
  getPaintProperty,
  update,
  setFilter,
  queryFeatures,
  queryRenderedFeatures,
  setPaintProperty,
  onZoom,
  changeSourceTilesUrl,
  setLayerVisibility,
  getSourceTilesUrl,
  filterLayers
})

watch(
  () => props.styleSpec,
  (styleSpec) => {
    map?.setStyle(styleSpec)
  },
  { immediate: true }
)

watch(
  () => props.popupLayerIds,
  (popupLayerIds) => {
    popupLayerIds.forEach((layerId) => {
      const popup = new Popup({
        closeButton: false,
        closeOnClick: false
      })
      map?.on('mouseenter', layerId, function () {
        if (map) {
          map.getCanvas().style.cursor = 'pointer'
        }
      })

      map?.on('mouseleave', layerId, function () {
        if (map) {
          map.getCanvas().style.cursor = ''
        }
        popup.remove()
      })
    })
  },
  { immediate: true }
)
watch(
  () => props.filterIds,
  (filterIds) => {
    filterLayers(filterIds)
  },
  { immediate: true }
)

function update(center?: LngLatLike, zoom?: number) {
  if (center !== undefined) {
    map?.setCenter(center)
  }
  if (zoom !== undefined) {
    map?.setZoom(zoom)
  }
}

function filterLayers(filterIds?: string[]) {
  if (filterIds && map !== undefined && map.isStyleLoaded()) {
    map
      .getStyle()
      .layers.filter((layer) => !layer.id.startsWith('gl-draw'))
      .forEach((layer) => {
        map?.setLayoutProperty(
          layer.id,
          'visibility',
          filterIds.includes(layer.id) ? 'visible' : 'none'
        )
      })
  }
}
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

.map:deep(.hovered-feature) {
  cursor: pointer !important;
}
</style>
