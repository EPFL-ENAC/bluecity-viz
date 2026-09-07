<script setup lang="ts">
import CVRPTooltip from '@/components/CVRPTooltip.vue'
import DeckGLOverlay from '@/components/DeckGLOverlay.vue'
import EdgeTooltip from '@/components/EdgeTooltip.vue'
import { useDeckGLCVRP } from '@/composables/useDeckGLCVRP'
import { useDeckGLTrafficAnalysis } from '@/composables/useDeckGLTrafficAnalysis'
import { useCVRPStore } from '@/stores/cvrp'
import { streetKey, useScenarioStore, type ScenarioAction } from '@/stores/scenario'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

// Everything deck.gl lives here, and this component is only mounted once a
// tool is opened. That is what keeps the 6 MB road network, and the deck.gl
// bundle itself, out of a page load where nobody asked for them.

const trafficStore = useTrafficAnalysisStore()
const cvrpStore = useCVRPStore()
const scenarioStore = useScenarioStore()

const deckGLTraffic = useDeckGLTrafficAnalysis()
const deckGLCVRP = useDeckGLCVRP(deckGLTraffic.edgeMap)

const edgeTooltip = ref<InstanceType<typeof EdgeTooltip> | null>(null)
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

function handleDeckClick(info: any) {
  deckGLTraffic.handleClick(info)
}

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

// Click cycling, kept until the on-map edit popover replaces it. It always
// covers both directions of the street, which is what the old click did.
const CYCLE: Array<ScenarioAction | null> = ['remove', '50', '30', '10', null]

function cycleStreet(u: number, v: number, name?: string) {
  const key = streetKey(u, v)
  const current = scenarioStore.get(key)
  const next = CYCLE[(CYCLE.indexOf(current?.action ?? null) + 1) % CYCLE.length]

  if (next === null) {
    scenarioStore.remove(key)
    return
  }
  scenarioStore.set(key, {
    action: next,
    dir: 'both',
    name: name || current?.name || `Edge ${u}→${v}`
  })
}

onMounted(async () => {
  deckGLTraffic.setTooltipMover((x, y) => edgeTooltip.value?.move(x, y))
  deckGLCVRP.setTooltipMover((x, y) => cvrpTooltip.value?.move(x, y))

  deckGLTraffic.setEdgeClickCallback(cycleStreet)

  // The layers are a computed over the store and the network, so results that
  // arrived before the geometry simply show up when the geometry lands.
  await deckGLTraffic.loadGraphEdges()
})

onUnmounted(() => {
  deckGLTraffic.setTooltipMover(null)
  deckGLCVRP.setTooltipMover(null)
})
</script>

<template>
  <div class="deck-analysis-layer">
    <DeckGLOverlay
      :layers="combinedLayers"
      :on-click="handleDeckClick"
      :on-hover="handleDeckHover"
    />

    <EdgeTooltip ref="edgeTooltip" :data="deckGLTraffic.tooltipData.value" />
    <CVRPTooltip ref="cvrpTooltip" :data="deckGLCVRP.cvrpTooltipData.value" />
  </div>
</template>
