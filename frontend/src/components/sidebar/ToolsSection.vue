<script setup lang="ts">
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { useCVRPStore } from '@/stores/cvrp'
import BcRow from '@/components/ui/BcRow.vue'

const trafficStore = useTrafficAnalysisStore()
const cvrpStore = useCVRPStore()

// The two tools are mutually exclusive: opening one closes the other.
function toggleTraffic() {
  if (!trafficStore.isOpen && cvrpStore.isOpen) cvrpStore.togglePanel()
  trafficStore.togglePanel()
}

function toggleCvrp() {
  if (!cvrpStore.isOpen && trafficStore.isOpen) trafficStore.togglePanel()
  cvrpStore.togglePanel()
}

const comingSoon = [
  { id: 'correlation', label: 'Correlation analysis' },
  { id: 'clustering', label: 'Spatial clustering' }
]
</script>

<template>
  <div class="bc-section bc-section--last">
    <div class="bc-micro tools__head">Analytics tools</div>

    <BcRow :on="trafficStore.isOpen" @click="toggleTraffic">
      Traffic analysis
      <template v-if="trafficStore.isOpen" #meta><span class="tools__meta">active</span></template>
    </BcRow>

    <BcRow :on="cvrpStore.isOpen" @click="toggleCvrp">
      Waste CVRP
      <template v-if="cvrpStore.isOpen" #meta><span class="tools__meta">active</span></template>
    </BcRow>

    <BcRow v-for="tool in comingSoon" :key="tool.id" disabled>
      {{ tool.label }}
      <template #meta><span class="tools__meta">soon</span></template>
    </BcRow>
  </div>
</template>

<style scoped>
.tools__head {
  margin-bottom: 6px;
}

.tools__meta {
  font-family: var(--bc-font-sans);
  font-size: var(--bc-fs-small);
  color: var(--bc-grey);
}

.bc-section--last {
  padding-bottom: 20px;
  border-bottom: 0;
}
</style>
