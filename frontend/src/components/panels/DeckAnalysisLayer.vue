<script setup lang="ts">
import CVRPTooltip from '@/components/CVRPTooltip.vue'
import DeckGLOverlay from '@/components/DeckGLOverlay.vue'
import { useDeckGLCVRP } from '@/composables/useDeckGLCVRP'
import { useDeckGLTrafficAnalysis } from '@/composables/useDeckGLTrafficAnalysis'
import { useCVRPStore } from '@/stores/cvrp'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

// Everything deck.gl lives here, and this component is only mounted once a
// tool is opened. That is what keeps the 6 MB road network, and the deck.gl
// bundle itself, out of a page load where nobody asked for them.

const trafficStore = useTrafficAnalysisStore()
const cvrpStore = useCVRPStore()

const deckGLTraffic = useDeckGLTrafficAnalysis()
const deckGLCVRP = useDeckGLCVRP(deckGLTraffic.edgeMap)

const cvrpTooltip = ref<InstanceType<typeof CVRPTooltip> | null>(null)

const anyToolOpen = computed(() => trafficStore.isOpen || cvrpStore.isOpen)

// When CVRP has results, hide the colored traffic route layers so they don't
// clutter the waste collection view. The grey base network and the
// modification markers stay, so the user still sees which edges are modified.
const combinedLayers = computed(() => {
  if (!anyToolOpen.value) return []

  const trafficLayers = cvrpStore.hasResult
    ? deckGLTraffic.layers.value.filter((l: any) => !l.id.startsWith('traffic-routes'))
    : deckGLTraffic.layers.value

  return [...trafficLayers, ...deckGLCVRP.layers.value]
})

// The CVRP route layer shows its own tooltip through its onHover, so the edge
// tooltip stands down while a CVRP result is on screen.
function handleDeckHover(info: any) {
  if (cvrpStore.hasResult) {
    deckGLTraffic.clearHover()
    return
  }
  deckGLTraffic.handleHover(info)
}

watch(
  () => cvrpStore.hasResult,
  (hasResult) => {
    if (hasResult) deckGLTraffic.clearHover()
    else deckGLCVRP.clearHover()
  }
)

// Nothing is highlighted while no tool is open
watch(anyToolOpen, (open) => {
  if (!open) {
    deckGLTraffic.clearHover()
    deckGLCVRP.clearHover()
  }
})

onMounted(async () => {
  deckGLCVRP.setTooltipMover((x, y) => cvrpTooltip.value?.move(x, y))

  // The layers are a computed over the store and the network, so results that
  // arrived before the geometry simply show up when the geometry lands.
  await deckGLTraffic.loadGraphEdges()
})

onUnmounted(() => {
  deckGLCVRP.setTooltipMover(null)
})
</script>

<template>
  <div class="deck-analysis-layer">
    <DeckGLOverlay :layers="combinedLayers" :on-hover="handleDeckHover" />

    <CVRPTooltip ref="cvrpTooltip" :data="deckGLCVRP.cvrpTooltipData.value" />
  </div>
</template>
