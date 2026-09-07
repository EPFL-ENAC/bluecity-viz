<script setup lang="ts">
import { MapboxOverlay } from '@deck.gl/mapbox'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { inject, onUnmounted, watch, type Ref } from 'vue'

const props = defineProps<{
  layers: any[]
  onClick?: (info: any, event: any) => void
  onHover?: (info: any, event: any) => void
}>()

// Get the MapLibre map instance from parent
const mapRef = inject<Ref<{ map?: MapLibreMap }>>('mapRef')

let deckOverlay: MapboxOverlay | null = null

const initializeOverlay = (map: MapLibreMap) => {
  // Don't reinitialize if already exists
  if (deckOverlay) {
    return
  }

  // Create Deck.gl overlay that syncs with MapLibre
  deckOverlay = new MapboxOverlay({
    interleaved: true,
    layers: props.layers,
    onClick: (info, event) => {
      if (props.onClick) {
        props.onClick(info, event)
      }
    },
    onHover: (info, event) => {
      if (props.onHover) {
        props.onHover(info, event)
      }
    },
    // Control cursor: return 'pointer' when hovering pickable object, otherwise let MapLibre handle it
    getCursor: ({ isHovering, isDragging }) => {
      if (isDragging) return 'grabbing'
      if (isHovering) return 'pointer'
      return 'grab'
    }
  })

  // Add overlay to MapLibre map
  try {
    map.addControl(deckOverlay as any)
  } catch (error) {
    console.warn('Could not add the Deck.gl overlay to the map', error)
    deckOverlay = null
  }
}

// The map is created asynchronously (MapLibreMap waits for the basemap tile URLs
// before `new Map()`), so wait for it instead of polling after mount.
watch(
  () => mapRef?.value?.map,
  (map) => {
    if (map) initializeOverlay(map)
  },
  { immediate: true }
)

// Watch for layer changes and update deck overlay
watch(
  () => props.layers,
  (newLayers) => {
    if (deckOverlay) {
      deckOverlay.setProps({ layers: newLayers })
    }
  }
)

onUnmounted(() => {
  if (deckOverlay && mapRef?.value?.map) {
    mapRef.value.map.removeControl(deckOverlay as any)
    deckOverlay.finalize()
    deckOverlay = null
  }
})

defineExpose({
  overlay: deckOverlay
})
</script>

<template>
  <!-- No visual element needed - overlay is added as MapLibre control -->
  <div style="display: none"></div>
</template>
