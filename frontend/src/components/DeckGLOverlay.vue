<script setup lang="ts">
import { MapboxOverlay } from '@deck.gl/mapbox'
import { onMounted, onUnmounted, watch, inject, type Ref, nextTick } from 'vue'
import type { Map as MapLibreMap } from 'maplibre-gl'

const props = defineProps<{
  layers: any[]
  onClick?: (info: any, event: any) => void
  onHover?: (info: any, event: any) => void
}>()

// Get the MapLibre map instance from parent
const mapRef = inject<Ref<{ map?: MapLibreMap }>>('mapRef')

let deckOverlay: MapboxOverlay | null = null

const initializeOverlay = () => {
  if (!mapRef?.value?.map) {
    console.warn('MapLibre map not available for Deck.gl overlay')
    return false
  }

  const map = mapRef.value.map

  // Don't reinitialize if already exists
  if (deckOverlay) {
    return true
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
    }
  })

  // Add overlay to MapLibre map
  map.addControl(deckOverlay as any)
  return true
}

onMounted(async () => {
  // Wait for next tick to ensure map is ready
  await nextTick()
  
  // Try to initialize, retry if map not ready
  const initialized = initializeOverlay()
  if (!initialized) {
    setTimeout(initializeOverlay, 100)
  }
})

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
