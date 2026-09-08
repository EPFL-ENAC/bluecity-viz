<script setup lang="ts">
import BcRow from '@/components/ui/BcRow.vue'
import BcSlider from '@/components/ui/BcSlider.vue'
import type { AreaFeedback } from '@/composables/useAreaPicker'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { computed } from 'vue'

// The circle itself lives on the map, drawn by useAreaPicker from the deck.gl
// layer list. This panel is the numbers and the two buttons.
const props = defineProps<{
  feedback: AreaFeedback
  canUse: boolean
  isChecking: boolean
  limits: { min_radius_m: number; max_radius_m: number }
}>()

const trafficStore = useTrafficAnalysisStore()

const radiusKm = computed({
  get: () => Math.round(((trafficStore.draftArea?.radiusM ?? 3000) / 1000) * 10) / 10,
  set: (km: number) => trafficStore.setDraftRadius(Math.round(km * 1000))
})

const minKm = computed(() => props.limits.min_radius_m / 1000)
const maxKm = computed(() => props.limits.max_radius_m / 1000)

const STATUS_LABEL: Record<string, string> = {
  ok: 'Usable here',
  too_sparse: 'Too sparse',
  too_large: 'Too large',
  disconnected: 'Not connected',
  outside_coverage: 'Outside Switzerland',
  unavailable: 'Not available here'
}

const STATUS_HINT: Record<string, string> = {
  ok: 'The tool can route inside this circle.',
  too_sparse: 'Not enough junctions for routing. Move over a town, or make the circle bigger.',
  too_large: 'More streets than the tool can route. Make the circle smaller.',
  disconnected: 'The streets here are in separate pieces. Move the circle a little.',
  outside_coverage: 'The road network only covers Switzerland.',
  unavailable: 'This server only has the default city, it cannot build another area.'
}

const statusLabel = computed(() => STATUS_LABEL[props.feedback.status] ?? 'Unknown')
const statusHint = computed(() => STATUS_HINT[props.feedback.status] ?? '')

const counts = computed(() => props.feedback.estimate)
const isExact = computed(() => props.feedback.exact !== null)

function formatCount(value: number): string {
  return value.toLocaleString('en-US')
}

const centre = computed(() => {
  const circle = trafficStore.draftArea
  if (!circle) return ''
  return `${circle.lat.toFixed(3)}, ${circle.lon.toFixed(3)}`
})
</script>

<template>
  <div class="dock-panel">
    <div class="dock-head">
      <div class="bc-micro">Traffic analysis</div>
      <div class="dock-title">Pick an area</div>
    </div>

    <div class="dock-section">
      <p class="bc-empty hint">Drag the circle on the map, or click where you want it.</p>

      <BcSlider
        v-model="radiusKm"
        :min="minKm"
        :max="maxKm"
        :step="0.5"
        label="Radius"
        :display="`${radiusKm} km`"
      />

      <div class="feedback" :data-status="feedback.status">
        <div class="feedback__chip">{{ statusLabel }}</div>
        <p class="feedback__hint">{{ statusHint }}</p>

        <div v-if="counts" class="feedback__counts">
          <div class="feedback__row">
            <span class="bc-micro">Junctions</span>
            <span class="feedback__value">{{ formatCount(counts.junctions) }}</span>
          </div>
          <div class="feedback__row">
            <span class="bc-micro">Streets</span>
            <span class="feedback__value">{{ formatCount(counts.edges) }}</span>
          </div>
          <div v-if="feedback.exact" class="feedback__row">
            <span class="bc-micro">One network</span>
            <span class="feedback__value">
              {{ Math.round(feedback.exact.scc_fraction * 100) }}%
            </span>
          </div>
        </div>

        <p class="bc-empty feedback__source">
          <template v-if="isChecking">Checking with the server…</template>
          <template v-else-if="isExact">Counted by the server. Centre {{ centre }}.</template>
          <template v-else>Estimated. Centre {{ centre }}.</template>
        </p>
      </div>
    </div>

    <div class="dock-section">
      <BcRow :check="false" :on="trafficStore.area === null" @click="trafficStore.useDefaultArea()">
        Lausanne (default)
      </BcRow>
    </div>

    <div class="dock-section">
      <p class="bc-empty warn">
        Changing the area clears the modified edges and the results. They belong to the streets of
        the current area.
      </p>
      <div class="actions">
        <button
          class="bc-btn bc-btn--primary"
          :disabled="!canUse"
          @click="trafficStore.exitPickMode(true)"
        >
          Use this area
        </button>
        <button class="bc-btn" @click="trafficStore.exitPickMode(false)">Cancel</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dock-head {
  padding: 18px 22px 14px;
  border-bottom: 1px solid var(--bc-line);
}

.dock-title {
  font-size: var(--bc-fs-title);
  font-weight: 300;
  letter-spacing: -0.01em;
  margin-top: 4px;
}

.dock-section {
  padding: 16px 22px;
  border-bottom: 1px solid var(--bc-line);
}

.hint {
  margin: 0 0 14px;
}

.feedback {
  margin-top: 16px;
  border-top: 1px solid var(--bc-line);
  padding-top: 12px;
}

.feedback__chip {
  display: inline-block;
  font-family: var(--bc-font-mono);
  font-size: var(--bc-fs-micro);
  letter-spacing: 0.04em;
  text-transform: uppercase;
  border: 1px solid var(--bc-ink);
  padding: 3px 8px;
}

.feedback[data-status='ok'] .feedback__chip {
  border-color: var(--bc-accent);
  color: var(--bc-accent);
}

.feedback:not([data-status='ok']) .feedback__chip {
  border-color: var(--bc-grey);
  color: var(--bc-grey);
}

.feedback__hint {
  margin: 8px 0 0;
  font-size: var(--bc-fs-body);
}

.feedback__counts {
  margin-top: 12px;
}

.feedback__row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding: 5px 0;
  border-top: 1px solid var(--bc-line);
}

.feedback__value {
  font-family: var(--bc-font-mono);
  font-size: var(--bc-fs-body);
}

.feedback__source {
  margin: 10px 0 0;
}

.warn {
  margin: 0 0 12px;
}

.actions {
  display: flex;
  gap: 8px;
}

.actions .bc-btn {
  flex: 1;
}
</style>
