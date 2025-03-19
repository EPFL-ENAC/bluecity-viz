import type { Map as MapLibre, MapLayerMouseEvent, Popup } from 'maplibre-gl'
import { Popup as MapLibrePopup } from 'maplibre-gl'
import { onUnmounted, ref, type Ref } from 'vue'

// Interface for tracking attached event listeners
interface EventListeners {
  [key: string]: {
    click?: (e: MapLayerMouseEvent) => void
    mousemove?: (e: MapLayerMouseEvent) => void
    mouseleave?: () => void
  }
}

// Helper function to format popup content
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

// Type definition for the return type to avoid inference issues
interface MapEventsReturn {
  hoveredFeature: Ref<Record<string, any> | null>
  selectedFeatureId: Ref<string | undefined>
  attachPopupListeners: (layerId: string, layerLabel: string) => void
  detachPopupListeners: (layerId: string) => void
  detachAllPopupListeners: () => void
  cleanup: () => void
}

/**
 * Composable for managing map layer event listeners and popups
 */
export function useMapEvents(
  mapRef: Ref<MapLibre | undefined>,
  popupOptions = {}
): MapEventsReturn {
  // State refs exposed by the composable
  const hoveredFeature = ref<Record<string, any> | null>(null)
  const selectedFeatureId = ref<string | undefined>(undefined)
  const clickedPopup = ref<Popup | null>(null)

  // Private state
  const currentFeatureId = ref<string | undefined>(undefined)
  const attachedEventListeners: EventListeners = {}

  // Initialize the hover popup with default + custom options
  const hoverPopup = new MapLibrePopup({
    closeButton: false,
    closeOnClick: false,
    maxWidth: '500px',
    className: 'feature-popup',
    ...popupOptions
  })

  /**
   * Handle layer click events
   */
  function handleLayerClick(_layerId: string, layerLabel: string, e: MapLayerMouseEvent): void {
    if (!e.features || e.features.length === 0 || !mapRef.value) return

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
    const persistentPopup = new MapLibrePopup({
      closeButton: true,
      closeOnClick: false,
      maxWidth: '500px',
      className: 'feature-popup persistent-popup'
    })

    // Format popup content
    const popupContent = formatPopupContent(feature.properties, layerLabel)

    // Add popup to the map
    persistentPopup.setLngLat(e.lngLat).setHTML(popupContent).addTo(mapRef.value)
    clickedPopup.value = persistentPopup

    // Remove the normal hover popup
    hoverPopup.remove()

    // Stop event propagation to prevent map click from closing it immediately
    e.preventDefault()
  }

  /**
   * Handle layer mousemove events
   */
  function handleLayerMouseMove(_layerId: string, layerLabel: string, e: MapLayerMouseEvent): void {
    if (!e.features || e.features.length === 0 || !mapRef.value) return

    const feature = e.features[0]
    mapRef.value.getCanvas().style.cursor = 'pointer'

    // Generate a unique ID for this feature
    const featureId =
      feature.id?.toString() ||
      JSON.stringify(feature.properties) +
        (feature.geometry.type === 'Point'
          ? feature.geometry.coordinates.toString()
          : e.lngLat.toString())

    // Only update if we've moved to a different feature
    if (currentFeatureId.value !== featureId) {
      currentFeatureId.value = featureId
      hoveredFeature.value = feature.properties

      // Format popup content
      const popupContent = formatPopupContent(feature.properties, layerLabel)

      hoverPopup.setLngLat(e.lngLat).setHTML(popupContent).addTo(mapRef.value)
    }
  }

  /**
   * Handle layer mouseleave events
   */
  function handleLayerMouseLeave(): void {
    if (!mapRef.value) return
    mapRef.value.getCanvas().style.cursor = ''
    currentFeatureId.value = undefined

    hoverPopup.remove()
    hoveredFeature.value = null
  }

  /**
   * Attach popup listeners to a layer
   */
  function attachPopupListeners(layerId: string, layerLabel: string): void {
    if (!mapRef.value) return

    // First detach any existing listeners for this layer
    detachPopupListeners(layerId)

    // Create bound handler functions
    const clickHandler = (e: MapLayerMouseEvent) => handleLayerClick(layerId, layerLabel, e)
    const mouseMoveHandler = (e: MapLayerMouseEvent) => handleLayerMouseMove(layerId, layerLabel, e)
    const mouseLeaveHandler = () => handleLayerMouseLeave()

    // Store handlers for later removal
    attachedEventListeners[layerId] = {
      click: clickHandler,
      mousemove: mouseMoveHandler,
      mouseleave: mouseLeaveHandler
    }

    // Attach event listeners to the map
    mapRef.value.on('click', layerId, clickHandler)
    mapRef.value.on('mousemove', layerId, mouseMoveHandler)
    mapRef.value.on('mouseleave', layerId, mouseLeaveHandler)
  }

  /**
   * Detach popup listeners from a layer
   */
  function detachPopupListeners(layerId: string): void {
    if (!mapRef.value) return

    const listeners = attachedEventListeners[layerId]
    if (!listeners) return

    // Remove each listener type if it exists
    if (listeners.click) {
      mapRef.value.off('click', layerId, listeners.click)
    }

    if (listeners.mousemove) {
      mapRef.value.off('mousemove', layerId, listeners.mousemove)
    }

    if (listeners.mouseleave) {
      mapRef.value.off('mouseleave', layerId, listeners.mouseleave)
    }

    // Remove from tracking object
    delete attachedEventListeners[layerId]
  }

  /**
   * Detach all popup listeners
   */
  function detachAllPopupListeners(): void {
    if (!mapRef.value) return

    Object.keys(attachedEventListeners).forEach((layerId) => {
      detachPopupListeners(layerId)
    })
  }

  /**
   * Clean up resources
   */
  function cleanup(): void {
    detachAllPopupListeners()

    if (hoverPopup) {
      hoverPopup.remove()
    }

    if (clickedPopup.value) {
      clickedPopup.value.remove()
      clickedPopup.value = null
    }

    hoveredFeature.value = null
    selectedFeatureId.value = undefined
    currentFeatureId.value = undefined
  }

  // Auto-cleanup when component unmounts
  onUnmounted(() => {
    cleanup()
  })

  // Return values and methods to be used by the component
  return {
    // State
    hoveredFeature,
    selectedFeatureId,

    // Methods
    attachPopupListeners,
    detachPopupListeners,
    detachAllPopupListeners,
    cleanup
  }
}
