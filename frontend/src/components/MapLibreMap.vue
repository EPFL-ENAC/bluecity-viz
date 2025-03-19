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
  type MapLayerMouseEvent,
  addProtocol
} from 'maplibre-gl'
import type { LegendColor } from '@/utils/legendColor'
import { onMounted, ref, watch } from 'vue'

import { Protocol } from 'pmtiles'
import { useApiKeyStore } from '@/stores/apiKey'
import { useLayersStore } from '@/stores/layers'

const apiKeyStore = useApiKeyStore()
const layersStore = useLayersStore()

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

const hoveredFeature = ref<Record<string, any> | null>(null)
// Create a popup for this layer
const popup = new Popup({
  closeButton: false,
  closeOnClick: false,
  maxWidth: '500px',
  className: 'feature-popup'
})
const selectedFeatureId = ref<string | undefined>(undefined)
const clickedPopup = ref<Popup | null>(null)

addProtocol('pmtiles', protocol.tile)

function initMap() {
  map = new Maplibre({
    container: container.value as HTMLDivElement,
    style: props.styleSpec,
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

    mapConfig.layers.forEach((layer) => attachPopupListeners(layer.layer.id, layer.label))

    map.on('sourcedata', handleDataEvent)

    map.on('sourcedataloading', handleDataEvent)

    filterSP0Period(layersStore.sp0Period)

    if (props.callbackLoaded) {
      props.callbackLoaded()
    }
  })
}

function formatPopupContent(properties: Record<string, any> | null, label: string): string {
  if (!properties) return 'No data available'

  // Create HTML table to display all properties
  let content = `<div class="popup-content"><h3>${label}</h3><table class="popup-table">`

  // Filter out null/undefined values and internal properties
  Object.entries(properties)
    .filter(
      ([key, value]) =>
        value !== null && value !== undefined && !key.startsWith('_') && key !== 'id' // Skip internal keys
    )
    .forEach(([key, value]) => {
      // Format the property key to be more readable
      const formattedKey = key
        .replace(/_/g, ' ')
        .replace(/([A-Z])/g, ' $1')
        .toLowerCase()
        .split(' ')
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ')

      // Format the value based on its type
      let formattedValue = value
      if (typeof value === 'number') {
        // Format numbers with up to 2 decimal places
        formattedValue = Math.round(value * 100) / 100
      }

      content += `
        <tr>
          <td class="property-name">${formattedKey}</td>
          <td class="property-value">${formattedValue}</td>
        </tr>
      `
    })

  content += '</table></div>'
  return content
}

// Function to attach popup listeners for a specific layer
function attachPopupListeners(layerId: string, layerLabel: string) {
  if (!map) return

  // Track the current feature to avoid duplicate popups
  let currentFeatureId: string | undefined = undefined

  // Add click event for this layer
  map.on('click', layerId, (e: MapLayerMouseEvent) => {
    if (!e.features || e.features.length === 0 || !map) return

    const feature = e.features[0]

    // Generate unique ID for clicked feature
    const featureId =
      feature.id?.toString() ||
      JSON.stringify(feature.properties) +
        (feature.geometry.type === 'Point'
          ? feature.geometry.coordinates.toString()
          : e.lngLat.toString())

    // Remove existing clicked popup if any
    if (clickedPopup.value) {
      clickedPopup.value.remove()
      clickedPopup.value = null
    }

    // Save this as the selected feature
    selectedFeatureId.value = featureId
    hoveredFeature.value = feature.properties

    // Create a new persistent popup
    const persistentPopup = new Popup({
      closeButton: true,
      closeOnClick: false,
      maxWidth: '500px',
      className: 'feature-popup persistent-popup'
    })

    // Format popup content
    const popupContent = formatPopupContent(feature.properties, layerLabel)

    // Add popup to the map
    persistentPopup.setLngLat(e.lngLat).setHTML(popupContent).addTo(map)
    clickedPopup.value = persistentPopup

    // Remove the normal hover popup
    popup.remove()

    // Stop event propagation to prevent map click from closing it immediately
    e.preventDefault()
  })

  // Add mousemove event for this layer
  map.on('mousemove', layerId, (e: MapLayerMouseEvent) => {
    if (!e.features || e.features.length === 0) return
    if (!map) return
    const feature = e.features[0]
    map.getCanvas().style.cursor = 'pointer'

    // Generate a unique ID for this feature
    const featureId =
      feature.id?.toString() ||
      JSON.stringify(feature.properties) +
        (feature.geometry.type === 'Point'
          ? feature.geometry.coordinates.toString()
          : e.lngLat.toString())

    // Only update if we've moved to a different feature
    if (currentFeatureId !== featureId) {
      currentFeatureId = featureId
      hoveredFeature.value = feature.properties

      // Format popup content
      const popupContent = formatPopupContent(feature.properties, layerLabel)

      popup.setLngLat(e.lngLat).setHTML(popupContent).addTo(map)
    }
  })

  map.on('mouseleave', layerId, () => {
    if (!map) return
    map.getCanvas().style.cursor = ''
    currentFeatureId = undefined

    popup.remove()
    hoveredFeature.value = null
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
  map?.setFilter(layerId, filter, options)
}

const getFilter = (layerId: string) => {
  return map?.getFilter(layerId)
}

const setPaintProperty = (
  layerId: string,
  name: string,
  value: any,
  options?: StyleSetterOptions | undefined
) => {
  map?.setPaintProperty(layerId, name, value, options)
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

function filterSP0Period(period: string) {
  const sp0Group = layersStore.layerGroups.find((group) => group.id === 'sp0_migration')

  if (!sp0Group) return
  sp0Group.layers
    .filter((layer) => {
      return layersStore.selectedLayers.includes(layer.layer.id)
    })
    .forEach((layer) => {
      const filter = ['==', ['get', 'year'], period] as FilterSpecification
      map?.setFilter(layer.layer.id, filter)
    })
}

// Filter SP0 migration layers by period
watch(
  () => [layersStore.sp0Period, layersStore.selectedLayers],
  ([newPeriod]) => filterSP0Period(newPeriod as string),
  { immediate: true }
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
      if (map?.getPitch() === 0) map?.easeTo({ pitch: 40, center: map?.getCenter() })
    } else if (had3DLayer && !has3DLayer) {
      map?.easeTo({ pitch: 0, center: map?.getCenter() })
    }
  }
)

defineExpose({
  getPaintProperty,
  update,
  setFilter,
  getFilter,
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
