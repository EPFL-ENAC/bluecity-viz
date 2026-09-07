<script setup lang="ts">
import CVRPTooltip from '@/components/CVRPTooltip.vue'
import DeckGLOverlay from '@/components/DeckGLOverlay.vue'
import { useDeckGLCVRP } from '@/composables/useDeckGLCVRP'
import { useGraphEdges } from '@/composables/useGraphEdges'
import { useCVRPStore } from '@/stores/cvrp'
import { computed, onMounted, onUnmounted, ref } from 'vue'

// What is left of deck.gl: the CVRP routes. The street graph, the result and
// the modifications are maplibre layers now (see GraphOverlay). This component
// is only mounted once a tool is opened, which keeps the deck.gl bundle out of
// a page load where nobody asked for it.

const cvrpStore = useCVRPStore()

const { edgeMap, loadGraphEdges } = useGraphEdges()
const deckGLCVRP = useDeckGLCVRP(edgeMap)

const cvrpTooltip = ref<InstanceType<typeof CVRPTooltip> | null>(null)

const layers = computed(() => (cvrpStore.isOpen ? deckGLCVRP.layers.value : []))

onMounted(async () => {
  deckGLCVRP.setTooltipMover((x, y) => cvrpTooltip.value?.move(x, y))
  await loadGraphEdges()
})

onUnmounted(() => {
  deckGLCVRP.setTooltipMover(null)
})
</script>

<template>
  <div class="deck-analysis-layer">
    <DeckGLOverlay :layers="layers" />

    <CVRPTooltip ref="cvrpTooltip" :data="deckGLCVRP.cvrpTooltipData.value" />
  </div>
</template>
