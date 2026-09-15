<script setup lang="ts">
import BcRow from '@/components/ui/BcRow.vue'
import { useCVRPStore } from '@/stores/cvrp'
import { useScenarioStore } from '@/stores/scenario'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'

// One row per tool. A click opens the dock on that tool, a click on the open one
// closes it. The two tools share the modified edges, each keeps its own result.
// The panel mirrors the open flag onto the two tool stores.
const scenarioStore = useScenarioStore()
const trafficStore = useTrafficAnalysisStore()
const cvrpStore = useCVRPStore()

type Tool = 'routing' | 'cvrp'

function isOpen(tool: Tool): boolean {
  return scenarioStore.isOpen && scenarioStore.activeTab === tool
}

function pick(tool: Tool): void {
  if (isOpen(tool)) {
    scenarioStore.isOpen = false
    return
  }
  scenarioStore.activeTab = tool
  scenarioStore.isOpen = true
}

/** Where the tool stands: not run, a short summary, or stale. */
function meta(tool: Tool): string {
  if (tool === 'routing') {
    if (!trafficStore.hasCalculatedRoutes) return ''
    if (trafficStore.isStale) return 'stale'
    return `${(trafficStore.resultOdPairs ?? 0).toLocaleString('en-US')} trips`
  }
  if (!cvrpStore.hasResult) return ''
  if (cvrpStore.isStale) return 'stale'
  const n = cvrpStore.lastResult?.n_routes ?? 0
  return `${n} route${n > 1 ? 's' : ''}`
}

const tools: { id: Tool; label: string }[] = [
  { id: 'routing', label: 'Routing' },
  { id: 'cvrp', label: 'Waste collection' }
]

const comingSoon = [
  { id: 'correlation', label: 'Correlation analysis' },
  { id: 'clustering', label: 'Spatial clustering' }
]
</script>

<template>
  <div class="bc-section bc-section--last">
    <div class="bc-micro tools__head">Analytics tools</div>

    <BcRow
      v-for="tool in tools"
      :key="tool.id"
      :on="isOpen(tool.id)"
      :active="isOpen(tool.id)"
      @click="pick(tool.id)"
    >
      {{ tool.label }}
      <template v-if="meta(tool.id)" #meta>
        <span class="tools__meta" :data-stale="meta(tool.id) === 'stale'">{{ meta(tool.id) }}</span>
      </template>
    </BcRow>
    <p class="tools__caption">Both tools run on the same area and the same modified streets.</p>

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

.tools__meta[data-stale='true'] {
  color: #b51f1f;
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
