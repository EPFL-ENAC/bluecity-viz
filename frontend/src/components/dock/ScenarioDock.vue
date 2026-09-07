<script setup lang="ts">
import CvrpTab from '@/components/dock/CvrpTab.vue'
import RoutingTab from '@/components/dock/RoutingTab.vue'
import BcIcon from '@/components/ui/BcIcon.vue'
import BcTabs, { type BcTab } from '@/components/ui/BcTabs.vue'
import { topAbsorbers, valueOf } from '@/composables/useResultStates'
import { useCVRPStore } from '@/stores/cvrp'
import { useLayersStore } from '@/stores/layers'
import { useScenarioStore } from '@/stores/scenario'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { computed } from 'vue'

/**
 * The scenario workbench.
 *
 * One dock, one scenario, two tools. The modified edges belong to the dock,
 * not to a tab: routing and waste collection both answer the same question
 * about the same graph, each keeps its own result and its own stale state.
 */

const emit = defineEmits<{ (event: 'hover-route', routeId: number | null): void }>()

const layersStore = useLayersStore()
const trafficStore = useTrafficAnalysisStore()
const cvrpStore = useCVRPStore()
const scenarioStore = useScenarioStore()

const title = computed(() => layersStore.activeInvestigation?.name ?? 'Road closure scenario')

// The badge in front of each modified edge: x to remove, else the speed limit.
function edgeBadge(action: string) {
  return action === 'remove' ? '×' : action
}

// ↔ both directions, → or ← one lane of the street.
const DIR_GLYPH: Record<string, string> = { both: '↔', fwd: '→', bwd: '←' }

/** What each tab says under its name: not run, a summary, or stale. */
const tabs = computed<BcTab[]>(() => [
  {
    id: 'routing',
    label: 'Routing',
    meta: trafficStore.isStale
      ? 'stale'
      : trafficStore.hasCalculatedRoutes
        ? `${trafficStore.resultOdPairs ?? 0} trips`
        : 'not run',
    stale: trafficStore.isStale
  },
  {
    id: 'cvrp',
    label: 'Waste CVRP',
    meta: cvrpStore.isStale
      ? 'stale'
      : cvrpStore.hasResult
        ? `${cvrpStore.lastResult?.n_routes ?? 0} vehicles`
        : 'not run',
    stale: cvrpStore.isStale
  }
])

// Once a result exists the rows carry a Δ bar in the same colour as the map.
const totalsByKey = computed(() => {
  const map = new Map<string, (typeof trafficStore.resultTotals)[number]>()
  for (const row of trafficStore.resultTotals) map.set(row.key, row)
  return map
})

const showDelta = computed(
  () => trafficStore.hasCalculatedRoutes && trafficStore.activeVisualization !== 'none'
)

interface DeltaRow {
  key: string
  value: number
  color: string
}

function deltaRow(key: string): DeltaRow | null {
  const totals = totalsByKey.value.get(key)
  if (!totals || !showDelta.value) return null
  const value = valueOf(totals, trafficStore.activeVisualization as never)
  const [r, g, b] = trafficStore.getColor(value)
  return { key, value, color: `rgb(${r},${g},${b})` }
}

const modifiedRows = computed<DeltaRow[]>(() =>
  scenarioStore.list.map((edge) => deltaRow(edge.key)).filter((row): row is DeltaRow => !!row)
)

/** Where the traffic went: the untouched streets that gained the most. */
const absorbers = computed(() => {
  if (!showDelta.value) return []
  const modified = new Set(scenarioStore.edgeModifications.keys())
  return topAbsorbers(trafficStore.resultTotals, modified).map((row) => {
    const value = valueOf(row, trafficStore.activeVisualization as never)
    const [r, g, b] = trafficStore.getColor(value)
    return { key: row.key, name: row.name, value, color: `rgb(${r},${g},${b})` }
  })
})

/** The widest value on screen, so the bars share one scale. */
const barMax = computed(() => {
  let max = 0
  for (const row of [...modifiedRows.value, ...absorbers.value]) {
    max = Math.max(max, Math.abs(row.value))
  }
  return max || 1
})

function barWidth(value: number): string {
  return `${Math.min(100, (Math.abs(value) / barMax.value) * 100)}%`
}

function deltaText(value: number): string {
  const sign = value > 0 ? '+' : ''
  return `${sign}${Math.round(value).toLocaleString('fr-CH').replace(/[\u202f\u00a0\u2009]/g, ' ')}`
}

function rowFor(key: string) {
  return modifiedRows.value.find((row) => row.key === key) ?? null
}
</script>

<template>
  <div class="dock-panel">
    <div class="dock-head">
      <div class="bc-micro">Scenario</div>
      <div class="dock-title">{{ title }}</div>
    </div>

    <!-- Modified edges -->
    <div class="dock-section">
      <div class="dock-section__head">
        <span class="bc-micro">Modified edges · {{ scenarioStore.count }}</span>
        <button
          v-if="scenarioStore.count > 0"
          class="bc-micro clear-btn"
          @click="scenarioStore.clear()"
        >
          Clear
        </button>
      </div>

      <div
        v-for="edge in scenarioStore.list"
        :key="edge.key"
        class="edge-row"
        :data-lit="scenarioStore.hovered?.key === edge.key"
        @mouseenter="scenarioStore.hover({ key: edge.key, dir: edge.dir })"
        @mouseleave="scenarioStore.hover(null)"
      >
        <span class="edge-row__badge">{{ edgeBadge(edge.action) }}</span>
        <span class="edge-row__name">{{ edge.name }}</span>
        <span class="edge-row__dir">{{ DIR_GLYPH[edge.dir] }}</span>
        <button
          class="edge-row__remove"
          title="Remove this modification"
          @click="scenarioStore.remove(edge.key)"
        >
          <BcIcon name="x" />
        </button>

        <div v-if="rowFor(edge.key)" class="edge-row__meta">
          <span class="edge-row__bar">
            <span
              class="edge-row__bar-fill"
              :style="{
                width: barWidth(rowFor(edge.key)!.value),
                background: rowFor(edge.key)!.color
              }"
            ></span>
          </span>
          <span class="edge-row__delta">{{ deltaText(rowFor(edge.key)!.value) }}</span>
        </div>
      </div>

      <p v-if="scenarioStore.count === 0" class="bc-empty edge-empty">
        Turn on Edit graph, then click an edge on the map.
      </p>

      <!-- Where the diverted traffic ended up -->
      <template v-if="absorbers.length">
        <div class="bc-micro absorb-head">Where the traffic went · top 3</div>
        <div
          v-for="row in absorbers"
          :key="row.key"
          class="edge-row edge-row--absorb"
          :data-lit="scenarioStore.hovered?.key === row.key"
          @mouseenter="scenarioStore.hover({ key: row.key, dir: 'both' })"
          @mouseleave="scenarioStore.hover(null)"
        >
          <span class="edge-row__name">{{ row.name || 'Unnamed street' }}</span>
          <div class="edge-row__meta">
            <span class="edge-row__bar">
              <span
                class="edge-row__bar-fill"
                :style="{ width: barWidth(row.value), background: row.color }"
              ></span>
            </span>
            <span class="edge-row__delta">{{ deltaText(row.value) }}</span>
          </div>
        </div>
      </template>

      <button
        class="edit-graph"
        type="button"
        @click="scenarioStore.setEditMode(!scenarioStore.editMode)"
      >
        <span class="edit-graph__dot" :data-on="scenarioStore.editMode"></span>
        {{ scenarioStore.editMode ? 'Leave edit mode' : 'Edit graph' }}
      </button>
    </div>


    <BcTabs v-model="scenarioStore.activeTab" :tabs="tabs" />

    <RoutingTab v-if="scenarioStore.activeTab === 'routing'" />
    <CvrpTab v-else @hover-route="(id) => emit('hover-route', id)" />
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

.dock-section__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 4px;
}

.dock-section__title {
  margin-bottom: 8px;
}

.clear-btn {
  background: none;
  border: 0;
  padding: 0;
  cursor: pointer;
}

.clear-btn:hover {
  color: var(--bc-ink);
}

.edge-row {
  display: grid;
  grid-template-columns: 34px 1fr auto 14px;
  gap: 10px;
  align-items: center;
  padding: 7px 0;
  border-top: 1px solid var(--bc-line);
  font-size: var(--bc-fs-body);
}

.edge-row[data-lit='true'] {
  background: var(--bc-hover);
  box-shadow: -3px 0 0 0 var(--bc-accent);
}

/* absorbers carry no badge, so the name takes the whole first line */
.edge-row--absorb {
  grid-template-columns: 1fr;
}

/* the Δ bar goes on a second line, full width */
.edge-row__meta {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}

.edge-row__bar {
  flex: 1;
  height: 3px;
  background: var(--bc-line);
  min-width: 0;
}

.edge-row__bar-fill {
  display: block;
  height: 100%;
}

.edge-row__delta {
  font-family: var(--bc-font-mono);
  font-size: var(--bc-fs-micro);
  font-variant-numeric: tabular-nums;
  color: var(--bc-grey);
  white-space: nowrap;
}

.absorb-head {
  margin-top: 14px;
  margin-bottom: 2px;
}

.edge-row__badge {
  font-family: var(--bc-font-mono);
  font-size: var(--bc-fs-micro);
  letter-spacing: 0.04em;
  border: 1px solid var(--bc-ink);
  text-align: center;
  padding: 2px 0;
}

.edge-row__name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.edge-row__dir {
  font-family: var(--bc-font-mono);
  font-size: var(--bc-fs-micro);
  color: var(--bc-grey);
}

.edge-row__remove {
  background: none;
  border: 0;
  padding: 0;
  color: var(--bc-grey);
  cursor: pointer;
  display: flex;
}

.edge-row__remove:hover {
  color: var(--bc-ink);
}

.edit-graph {
  margin-top: 10px;
  width: 100%;
  font-family: var(--bc-font-mono);
  font-size: 10.5px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  background: transparent;
  color: var(--bc-ink);
  border: 1px solid var(--bc-ink);
  padding: 9px 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: background var(--bc-t);
}

.edit-graph:hover {
  background: var(--bc-hover);
}

.edit-graph__dot {
  width: 5px;
  height: 5px;
  background: var(--bc-accent);
  flex: none;
}

.edit-graph__dot[data-on='true'] {
  background: var(--bc-ink);
}

.edge-empty {
  margin: 8px 0 0;
}

.info-icon {
  display: flex;
  cursor: help;
}

.iterations {
  padding: 8px 0 4px 21px;
}

.iterations__label {
  font-size: var(--bc-fs-small);
  color: var(--bc-grey);
  margin-bottom: 2px;
}

.trips {
  margin-top: 14px;
}

.trips__label {
  margin-bottom: 6px;
}

/* no switching while a run is in flight, the answer would be for the old count */
.trips__seg--busy {
  opacity: 0.5;
  pointer-events: none;
}

.trips__warning {
  font-family: var(--bc-font-mono);
  font-size: var(--bc-fs-micro);
  line-height: 1.5;
  color: var(--bc-grey);
  margin: 6px 0 0;
}

.calculate {
  margin-top: 14px;
  width: 100%;
}

.calculate:disabled {
  opacity: 0.5;
  cursor: default;
}

.calculate__progress {
  margin-top: 8px;
}

.calculate__msg {
  margin-top: 6px;
}

.vis-row {
  padding-left: 12px;
}

.clip {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: var(--bc-grey);
}

.clip__chip {
  font-family: var(--bc-font-mono);
  font-size: var(--bc-fs-micro);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  border: 1px solid var(--bc-ink);
  color: var(--bc-ink);
  padding: 3px 8px;
  cursor: pointer;
  transition:
    background var(--bc-t),
    color var(--bc-t);
}

.clip__chip[data-on='true'] {
  background: var(--bc-ink);
  color: var(--bc-ground);
}
</style>
