<script setup lang="ts">
/**
 * Scenario | Result, top left of the map.
 *
 * The two never stack: either you are editing the graph in ink, or you are
 * reading the result in colour. The toggle says which one you are looking at.
 */
import { useCVRPStore } from '@/stores/cvrp'
import { useScenarioStore } from '@/stores/scenario'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { computed } from 'vue'

const scenarioStore = useScenarioStore()
const trafficStore = useTrafficAnalysisStore()
const cvrpStore = useCVRPStore()

const hasResult = computed(() => trafficStore.hasCalculatedRoutes || cvrpStore.hasResult)

// Which tool the colours on the map come from.
const resultLabel = computed(() => {
  if (trafficStore.hasCalculatedRoutes && cvrpStore.hasResult) return 'Result'
  if (cvrpStore.hasResult) return 'Result · CVRP'
  if (trafficStore.hasCalculatedRoutes) return 'Result · Routing'
  return 'Result'
})

const stale = computed(() => trafficStore.isStale || cvrpStore.isStale)
</script>

<template>
  <div v-if="hasResult" class="mode">
    <button
      class="mode__btn"
      type="button"
      :data-on="scenarioStore.mapMode === 'scenario'"
      @click="scenarioStore.mapMode = 'scenario'"
    >
      Scenario
    </button>
    <button
      class="mode__btn"
      type="button"
      :data-on="scenarioStore.mapMode === 'result'"
      @click="scenarioStore.mapMode = 'result'"
    >
      {{ resultLabel }}<span v-if="stale" class="mode__stale"> · stale</span>
    </button>
  </div>
</template>

<style scoped>
.mode {
  position: absolute;
  left: 16px;
  top: 16px;
  z-index: 3;
  display: flex;
  border: 1px solid var(--bc-ink);
  background: var(--bc-legend-bg);
  pointer-events: auto;
}

.mode__btn {
  font-family: var(--bc-font-mono);
  font-size: var(--bc-fs-micro);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 6px 12px;
  border: 0;
  border-left: 1px solid var(--bc-ink);
  background: transparent;
  color: var(--bc-ink);
  cursor: pointer;
  white-space: nowrap;
}

.mode__btn:first-child {
  border-left: 0;
}

.mode__btn[data-on='true'] {
  background: var(--bc-ink);
  color: var(--bc-ground);
}

.mode__stale {
  color: #b51f1f;
}

.mode__btn[data-on='true'] .mode__stale {
  color: #ff8a8a;
}
</style>
