<script lang="ts">
// Sentence-case labels, per the design. Falls back to the store label.
const VIS_LABELS: Record<string, string> = {
  frequency: 'Edge usage frequency',
  co2: 'CO₂ emissions',
  delta: 'Traffic change (Δ)',
  delta_relative: 'Traffic change (Δ, relative %)',
  co2_delta: 'CO₂ emissions change',
  betweenness: 'Betweenness centrality',
  betweenness_delta: 'Betweenness change'
}

export function visLabel(mode: string, fallback: string): string {
  return VIS_LABELS[mode] ?? fallback
}
</script>

<script setup lang="ts">
import BcRow from '@/components/ui/BcRow.vue'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'

/**
 * The layers the map can draw, one row each, the active one lit.
 *
 * The Model and the Results steps share it. The store offers what the rows on
 * screen can draw, so the Model state gets no change layer with no special
 * case here.
 */

const trafficStore = useTrafficAnalysisStore()
</script>

<template>
  <BcRow
    v-for="vis in trafficStore.availableVisualizations"
    :key="vis.value"
    :check="false"
    :on="trafficStore.activeVisualization === vis.value"
    :active="trafficStore.activeVisualization === vis.value"
    class="vis-row"
    @click="trafficStore.setActiveVisualization(vis.value)"
  >
    {{ visLabel(vis.value, vis.label) }}
  </BcRow>
</template>

<style scoped>
.vis-row {
  padding-left: 12px;
}
</style>
