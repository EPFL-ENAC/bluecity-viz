<script setup lang="ts">
import { Deck } from '@deck.gl/core'
import { TileLayer } from '@deck.gl/geo-layers'
import { BitmapLayer } from '@deck.gl/layers'
import { onMounted, onUnmounted, watch, ref } from 'vue'

const props = defineProps<{
  layers: any[]
  viewState?: any
  onClick?: (info: any, event: any) => void
  onHover?: (info: any, event: any) => void
  showBasemap?: boolean
}>()

const emit = defineEmits<{
  viewStateChange: [viewState: any]
}>()

const container = ref<HTMLDivElement | null>(null)
let deck: Deck | null = null

// Create basemap tile layer once and reuse it
const basemapLayer = new TileLayer({
  id: 'basemap-tiles',
  data: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
  minZoom: 0,
  maxZoom: 19,
  tileSize: 256,
  renderSubLayers: (props: any) => {
    const {
      bbox: { west, south, east, north }
    } = props.tile

    return new BitmapLayer(props, {
      data: undefined,
      image: props.data,
      bounds: [west, south, east, north]
    })
  }
})

onMounted(() => {
  if (!container.value) return

  const allLayers = props.showBasemap !== false ? [basemapLayer, ...props.layers] : props.layers

  // Initialize Deck.gl instance
  deck = new Deck({
    canvas: container.value.querySelector('canvas') || undefined,
    width: '100%',
    height: '100%',
    initialViewState: props.viewState || {
      longitude: 6.63,
      latitude: 46.52,
      zoom: 11,
      pitch: 0,
      bearing: 0
    },
    controller: true,
    layers: allLayers,
    onClick: (info, event) => {
      if (props.onClick) {
        props.onClick(info, event)
      }
    },
    onViewStateChange: ({ viewState }) => {
      emit('viewStateChange', viewState)
    }
  })
})

// Watch for layer changes and update deck
watch(
  () => props.layers,
  (newLayers) => {
    if (deck) {
      const allLayers = props.showBasemap !== false ? [basemapLayer, ...newLayers] : newLayers
      deck.setProps({ layers: allLayers })
    }
  }
)

// Watch for view state changes
watch(
  () => props.viewState,
  (newViewState) => {
    if (deck && newViewState) {
      deck.setProps({ initialViewState: newViewState })
    }
  }
)

onUnmounted(() => {
  if (deck) {
    deck.finalize()
    deck = null
  }
})

defineExpose({
  deck
})
</script>

<template>
  <div ref="container" class="deckgl-overlay">
    <canvas />
  </div>
</template>

<style scoped>
.deckgl-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: all;
  z-index: 1;
  background-color: #f0f0f0;
}

.deckgl-overlay canvas {
  width: 100%;
  height: 100%;
}
</style>
