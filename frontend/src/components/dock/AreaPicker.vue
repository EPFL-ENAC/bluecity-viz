<script setup lang="ts">
import BcRow from '@/components/ui/BcRow.vue'
import BcSeg from '@/components/ui/BcSeg.vue'
import BcSlider from '@/components/ui/BcSlider.vue'
import type { AreaFeedback } from '@/composables/useAreaFeedback'
import type { AreaOutline } from '@/services/trafficAnalysis'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { communeName, type CommuneIndex } from '@/utils/municipalities'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { computed, inject, onUnmounted, ref, watch, type Ref } from 'vue'

// The shape itself lives on the map, drawn by AreaPickerOverlay. This panel
// is the mode, the numbers and the two buttons.
const props = defineProps<{
  feedback: AreaFeedback
  canUse: boolean
  isChecking: boolean
  limits: {
    min_radius_m: number
    max_radius_m: number
    has_municipalities?: boolean
  }
  communes: CommuneIndex | null
  outline: AreaOutline | null
}>()

const trafficStore = useTrafficAnalysisStore()

const mapComponentRef = inject<Ref<{ map?: MapLibreMap } | undefined>>('mapRef')
const map = computed(() => mapComponentRef?.value?.map)

type Kind = 'circle' | 'municipalities'

const kind = computed<Kind>(() => trafficStore.draftArea?.kind ?? 'circle')

// Hidden only when the server says it has no boundaries, not while it has
// not answered yet.
const KIND_OPTIONS = [
  { value: 'circle', label: 'Radius' },
  { value: 'municipalities', label: 'Municipalities' }
]
const showKinds = computed(() => props.limits.has_municipalities !== false)

function setKind(value: string): void {
  if (value !== 'circle' && value !== 'municipalities') return
  const centre = map.value?.getCenter()
  trafficStore.setDraftKind(value, centre ? { lon: centre.lng, lat: centre.lat } : undefined)
}

const picked = computed(() => {
  const draft = trafficStore.draftArea
  if (draft?.kind !== 'municipalities') return []
  return draft.ofsIds.map((id) => ({ id, name: communeName(id, props.communes) }))
})

// Under this zoom the communes are too small to click one on purpose.
const PICK_ZOOM = 9
const zoom = ref(map.value?.getZoom() ?? PICK_ZOOM)

function readZoom(): void {
  const current = map.value
  if (current) zoom.value = current.getZoom()
}

watch(
  map,
  (current, previous) => {
    previous?.off('zoomend', readZoom)
    current?.on('zoomend', readZoom)
    readZoom()
  },
  { immediate: true }
)

onUnmounted(() => map.value?.off('zoomend', readZoom))

const radiusKm = computed({
  get: () => {
    const draft = trafficStore.draftArea
    const radiusM = draft?.kind === 'circle' ? draft.radiusM : 3000
    return Math.round((radiusM / 1000) * 10) / 10
  },
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
  not_contiguous: 'Not touching',
  unavailable: 'Not available here',
  empty: 'Nothing selected',
  checking: 'Checking…'
}

const STATUS_HINT: Record<Kind, Record<string, string>> = {
  circle: {
    ok: 'The tool can route inside this circle.',
    too_sparse: 'Not enough junctions for routing. Move over a town, or make the circle bigger.',
    too_large: 'More streets than the tool can route. Make the circle smaller.',
    disconnected: 'The streets here are in separate pieces. Move the circle a little.',
    outside_coverage: 'The road network only covers Switzerland.',
    unavailable: 'This server only has the default city, it cannot build another area.'
  },
  municipalities: {
    ok: 'The tool can route inside these municipalities.',
    too_sparse: 'These municipalities have too few junctions. Add a neighbour.',
    too_large: 'More streets than the tool can route. Remove a municipality.',
    disconnected: 'The streets of this area are in separate pieces.',
    outside_coverage: 'No road network for this municipality.',
    not_contiguous: 'Every municipality must share a border with the others.',
    unavailable: 'This server cannot build an area from municipalities.',
    empty: 'Pick at least one municipality.',
    checking: 'The server is counting the streets.'
  }
}

const statusLabel = computed(() => STATUS_LABEL[props.feedback.status] ?? 'Unknown')
const statusHint = computed(() => STATUS_HINT[kind.value][props.feedback.status] ?? '')

const counts = computed(() => props.feedback.estimate)
const isExact = computed(() => props.feedback.exact !== null)

function formatCount(value: number): string {
  return value.toLocaleString('en-US')
}

const centre = computed(() => {
  const circle = trafficStore.draftArea
  if (circle?.kind !== 'circle') return ''
  return `${circle.lat.toFixed(3)}, ${circle.lon.toFixed(3)}`
})

// The place the circle sits on, read from the basemap by AreaPickerOverlay.
// Empty on a style with no labels, and then only the coordinates show.
const placeName = computed(() => trafficStore.draftArea?.name ?? '')

const sourceShape = computed(() => {
  if (kind.value === 'circle') return `Centre ${centre.value}.`
  const count = picked.value.length
  return `${count} ${count === 1 ? 'municipality' : 'municipalities'}.`
})
</script>

<template>
  <div class="dock-panel">
    <div class="dock-head">
      <div class="bc-micro">Scenario</div>
      <div class="dock-title">Pick an area</div>
    </div>

    <div class="dock-section">
      <BcSeg
        v-if="showKinds"
        class="kinds"
        :model-value="kind"
        :options="KIND_OPTIONS"
        equal
        @update:model-value="setKind"
      />

      <template v-if="kind === 'circle'">
        <p class="bc-empty hint">Drag the circle on the map, or click where you want it.</p>

        <BcSlider
          v-model="radiusKm"
          :min="minKm"
          :max="maxKm"
          :step="0.5"
          label="Radius"
          :display="`${radiusKm} km`"
        />
      </template>

      <template v-else>
        <p class="bc-empty hint">
          Click a municipality on the map to add it. Click again to remove it.
        </p>
        <p v-if="zoom < PICK_ZOOM" class="bc-empty hint">Zoom in to pick a municipality.</p>

        <div class="picked">
          <BcRow v-for="commune in picked" :key="commune.id" :check="false" on>
            {{ commune.name }}
            <template #trailing>
              <button
                class="bc-micro picked__remove"
                @click.stop="trafficStore.removeDraftMunicipality(commune.id)"
              >
                Remove
              </button>
            </template>
          </BcRow>
        </div>
      </template>

      <div class="feedback" :data-status="feedback.status">
        <div class="feedback__chip">{{ statusLabel }}</div>
        <p v-if="placeName" class="feedback__place">{{ placeName }}</p>
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

        <p v-if="kind === 'circle' || picked.length" class="bc-empty feedback__source">
          <template v-if="isChecking">Checking with the server…</template>
          <template v-else-if="isExact">Counted by the server. {{ sourceShape }}</template>
          <template v-else-if="kind === 'circle'">Estimated. {{ sourceShape }}</template>
          <template v-else>{{ sourceShape }}</template>
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
          @click="trafficStore.exitPickMode(true, outline)"
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

.kinds {
  margin-bottom: 14px;
}

.picked {
  border-bottom: 1px solid var(--bc-line);
}

.picked:empty {
  display: none;
}

.picked__remove {
  background: none;
  border: 0;
  padding: 0;
  color: var(--bc-grey);
  cursor: pointer;
}

.picked__remove:hover {
  color: var(--bc-ink);
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

/* The name of the place, the answer to "where am I" before the numbers. */
.feedback__place {
  margin: 10px 0 0;
  font-size: var(--bc-fs-title);
  font-weight: 300;
  letter-spacing: -0.01em;
  line-height: 1.15;
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
