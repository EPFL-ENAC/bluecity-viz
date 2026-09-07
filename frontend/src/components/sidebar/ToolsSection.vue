<script setup lang="ts">
import BcRow from '@/components/ui/BcRow.vue'
import { useScenarioStore } from '@/stores/scenario'

// One row, one dock. Routing and waste collection are two tabs of the same
// workbench because they answer the same question about the same graph. The
// panel mirrors this flag onto the two tool stores.
const scenarioStore = useScenarioStore()

function toggleWorkbench() {
  scenarioStore.isOpen = !scenarioStore.isOpen
}

const comingSoon = [
  { id: 'correlation', label: 'Correlation analysis' },
  { id: 'clustering', label: 'Spatial clustering' }
]
</script>

<template>
  <div class="bc-section bc-section--last">
    <div class="bc-micro tools__head">Analytics tools</div>

    <BcRow :on="scenarioStore.isOpen" @click="toggleWorkbench">
      Scenario workbench
      <template v-if="scenarioStore.isOpen" #meta><span class="tools__meta">active</span></template>
    </BcRow>
    <p class="tools__caption">Routing · Waste CVRP, one dock, one scenario, two tools.</p>

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

.tools__caption {
  margin: 4px 0 8px;
  font-size: var(--bc-fs-small);
  color: var(--bc-grey);
}

.bc-section--last {
  padding-bottom: 20px;
  border-bottom: 0;
}
</style>
