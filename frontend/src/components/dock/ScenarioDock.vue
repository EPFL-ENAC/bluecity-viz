<script setup lang="ts">
import AreaPicker from '@/components/dock/AreaPicker.vue'
import CvrpTab from '@/components/dock/CvrpTab.vue'
import RoutingTab from '@/components/dock/RoutingTab.vue'
import BcIcon from '@/components/ui/BcIcon.vue'
import BcSeg from '@/components/ui/BcSeg.vue'
import BcSlider from '@/components/ui/BcSlider.vue'
import BcTabs, { type BcTab } from '@/components/ui/BcTabs.vue'
import { useAreaFeedback } from '@/composables/useAreaFeedback'
import { useGraphEdges } from '@/composables/useGraphEdges'
import { useMapView } from '@/composables/useMapView'
import { topAbsorbers, valueOf } from '@/composables/useResultStates'
import { useCVRPStore } from '@/stores/cvrp'
import { useLayersStore } from '@/stores/layers'
import {
  useScenarioStore,
  type ScenarioAction,
  type ScenarioDir
} from '@/stores/scenario'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import type { Map as MapLibre } from 'maplibre-gl'
import { computed, inject, ref, type Ref } from 'vue'

/**
 * The scenario workbench.
 *
 * One dock, one scenario, two tools. The modified edges belong to the dock,
 * not to a tab: routing and waste collection both answer the same question
 * about the same graph, each keeps its own result and its own stale state.
 */

const emit = defineEmits<{
  (event: 'hover-route', routeId: number | null): void
  (event: 'focus', keys: string[]): void
}>()

const layersStore = useLayersStore()
const trafficStore = useTrafficAnalysisStore()
const cvrpStore = useCVRPStore()
const scenarioStore = useScenarioStore()
const { dimmed } = useMapView()
const areaFeedback = useAreaFeedback()
const mapRef = inject<Ref<{ map?: MapLibre } | undefined>>('mapRef')

/**
 * The dock has two zones and the map draws the lit one: the ink scenario on
 * top, the tool below. Clicking anywhere in the dimmed zone lights it, and the
 * click still goes through, so nothing needs a second try.
 */
function light(zone: 'scenario' | 'tool'): void {
  scenarioStore.mapMode = zone === 'scenario' ? 'scenario' : 'result'
}

// The area the workbench runs on.
const areaName = computed(() => {
  const circle = trafficStore.area
  if (!circle) return 'Lausanne (default)'
  // The name the picker read on the basemap. Areas saved before that, and the
  // styles with no labels, still show the circle itself.
  if (circle.name) return circle.name
  const km = (circle.radiusM / 1000).toFixed(1)
  return `${km} km around ${circle.lat.toFixed(3)}, ${circle.lon.toFixed(3)}`
})

// The circle behind the name, so the radius stays readable.
const areaShape = computed(() => {
  const circle = trafficStore.area
  if (!circle?.name) return ''
  const km = (circle.radiusM / 1000).toFixed(1)
  return `${km} km around ${circle.lat.toFixed(3)}, ${circle.lon.toFixed(3)}`
})

// The streets of this area are not on the map yet. The ring is already
// there, so the dock says why it is empty instead of looking broken.
const { edges: graphEdges } = useGraphEdges()
const areaStatus = computed(() => {
  if (trafficStore.areaError) return null
  if (trafficStore.isBuildingArea) return 'Building the network for this area…'
  if (graphEdges.value.length === 0) return 'Loading the streets…'
  return null
})

/** Open the picker on the circle we have, or on what the map is looking at. */
function changeArea(): void {
  const centre = mapRef?.value?.map?.getCenter()
  trafficStore.enterPickMode(centre ? { lon: centre.lng, lat: centre.lat } : undefined)
}

/** Fit the map on the modified streets, or on one of them. */
function focus(keys: string[]): void {
  if (keys.length) emit('focus', keys)
}

const title = computed(() => layersStore.activeInvestigation?.name ?? 'Road closure scenario')

// The badge in front of each modified edge: x to remove, else the speed limit.
function edgeBadge(action: string) {
  return action === 'remove' ? '×' : action
}

// ↔ both directions, → or ← one lane of the street.
const DIR_GLYPH: Record<string, string> = { both: '↔', fwd: '→', bwd: '←' }

/** The three ways to pick streets. The letters are the keyboard shortcuts. */
const TOOLS = [
  { value: 'pointer', label: 'Point' },
  { value: 'lasso', label: 'Lasso L' },
  { value: 'brush', label: 'Brush B' }
]

const TOOL_NOTE: Record<string, string> = {
  pointer: 'Click a street, ⇧-click to add more',
  lasso: 'Draw around the streets on screen',
  brush: 'Paint along the streets, [ and ] resize'
}

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

// The bars read the routing result, so they follow the tab, not the lit zone.
const showDelta = computed(
  () =>
    scenarioStore.activeTab === 'routing' &&
    trafficStore.hasCalculatedRoutes &&
    trafficStore.activeVisualization !== 'none'
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
  return `${sign}${Math.round(value)
    .toLocaleString('fr-CH')
    .replace(/[\u202f\u00a0\u2009]/g, ' ')}`
}

function rowFor(key: string) {
  return modifiedRows.value.find((row) => row.key === key) ?? null
}

/** The action buttons of a group row, the same four as in the map popover. */
const ACTION_OPTIONS = [
  { value: 'remove', label: '×' },
  { value: '50', label: '50' },
  { value: '30', label: '30' },
  { value: '10', label: '10' }
]

const DIR_OPTIONS = [
  { value: 'both', label: '↔' },
  { value: 'fwd', label: '→' },
  { value: 'bwd', label: '←' }
]

// BcSeg speaks in plain strings, the store wants its own unions.
function groupAction(id: string, value: string): void {
  scenarioStore.setGroup(id, { action: value as ScenarioAction })
}

function groupDir(id: string, value: string): void {
  scenarioStore.setGroup(id, { dir: value as ScenarioDir })
}

/** Which groups show their streets. */
const expanded = ref(new Set<string>())

function toggleGroup(id: string): void {
  const next = new Set(expanded.value)
  if (!next.delete(id)) next.add(id)
  expanded.value = next
}

/** A group row lights up when the map points at any of its streets. */
function litGroup(keys: string[]): boolean {
  return keys.some((key) => scenarioStore.hoveredSet.has(key))
}
</script>

<template>
  <AreaPicker
    v-if="trafficStore.pickMode"
    :feedback="areaFeedback.feedback.value"
    :can-use="areaFeedback.canUse.value"
    :is-checking="areaFeedback.isChecking.value"
    :limits="areaFeedback.limits.value"
  />

  <div v-else class="dock-panel">
    <div class="dock-head">
      <div class="bc-micro">Scenario</div>
      <div class="dock-title">{{ title }}</div>
    </div>

    <!-- The area both tools run on. Not a zone: it is neither the scenario
         nor a result, and it never dims. -->
    <div class="dock-section">
      <div class="dock-section__head">
        <span class="bc-micro">Area</span>
        <button class="bc-micro clear-btn" @click="changeArea">Change area</button>
      </div>
      <div class="area-name">{{ areaName }}</div>
      <p v-if="areaShape" class="bc-empty area-note">{{ areaShape }}</p>
      <p v-if="areaStatus" class="bc-empty area-note">{{ areaStatus }}</p>
      <p v-if="trafficStore.areaError" class="bc-empty area-error">
        {{ trafficStore.areaError.message }}
      </p>
    </div>

    <!-- Modified edges: the scenario zone -->
    <section
      class="dock-section zone"
      :data-dim="dimmed === 'scenario'"
      :data-lit="dimmed === 'tool'"
      @pointerdown.capture="light('scenario')"
      @focusin="light('scenario')"
    >
      <!-- How the pointer picks streets. Click one, draw a lasso around a
           block, or paint along an axis. -->
      <div class="tools">
        <BcSeg v-model="scenarioStore.tool" :options="TOOLS" equal />
        <BcSlider
          v-if="scenarioStore.tool === 'brush'"
          v-model="scenarioStore.brushRadius"
          :min="8"
          :max="80"
          :step="2"
          label="Brush width"
          :display="`${scenarioStore.brushRadius} px`"
        />
        <p class="bc-micro tools__note">{{ TOOL_NOTE[scenarioStore.tool] }}</p>
      </div>

      <div class="dock-section__head">
        <span class="bc-micro">Modified edges · {{ scenarioStore.count }}</span>
        <span v-if="scenarioStore.count > 0" class="head-actions">
          <button
            class="focus-btn"
            type="button"
            title="Fit the map on the modified streets"
            @click="focus(scenarioStore.list.map((edge) => edge.key))"
          >
            <BcIcon name="map-pin" />
          </button>
          <button class="bc-micro clear-btn" @click="scenarioStore.clear()">Clear</button>
        </span>
      </div>

      <template v-for="row in scenarioStore.dockRows">
        <!-- A group: the streets of one lasso or one brush stroke, edited
             together and shown as one row. -->
        <template v-if="row.kind === 'group'">
          <div
            :key="row.group.id"
            class="edge-row edge-row--group edge-row--click"
            :data-lit="litGroup(row.group.keys)"
            title="Zoom to these streets"
            @click="focus(row.group.keys)"
            @mouseenter="scenarioStore.hover({ keys: row.group.keys, dir: row.group.dir })"
            @mouseleave="scenarioStore.hover(null)"
          >
            <span class="edge-row__badge">{{ edgeBadge(row.group.action) }}</span>
            <span class="edge-row__name">{{ row.group.label }}</span>
            <span class="edge-row__dir">{{ DIR_GLYPH[row.group.dir] }}</span>
            <button
              class="edge-row__remove"
              title="Remove this group"
              @click.stop="scenarioStore.removeGroup(row.group.id)"
            >
              <BcIcon name="x" />
            </button>

            <div class="edge-row__group" @click.stop>
              <BcSeg
                :model-value="row.group.action"
                :options="ACTION_OPTIONS"
                equal
                @update:model-value="(value) => groupAction(row.group.id, value)"
              />
              <BcSeg
                v-if="row.group.anyTwoWay"
                :model-value="row.group.dir"
                :options="DIR_OPTIONS"
                equal
                @update:model-value="(value) => groupDir(row.group.id, value)"
              />
              <button class="bc-micro clear-btn group-toggle" @click="toggleGroup(row.group.id)">
                {{ expanded.has(row.group.id) ? 'Hide streets' : 'Show streets' }}
              </button>
            </div>
          </div>

          <div
            v-for="key in expanded.has(row.group.id) ? row.group.keys : []"
            :key="`${row.group.id}-${key}`"
            class="edge-row edge-row--child edge-row--click"
            :data-lit="scenarioStore.hoveredSet.has(key)"
            title="Zoom to this street"
            @click="focus([key])"
            @mouseenter="scenarioStore.hover({ keys: [key], dir: row.group.dir })"
            @mouseleave="scenarioStore.hover(null)"
          >
            <span class="edge-row__name">{{ scenarioStore.get(key)?.name || key }}</span>
            <button
              class="edge-row__remove"
              title="Take this street out of the group"
              @click.stop="scenarioStore.remove(key)"
            >
              <BcIcon name="x" />
            </button>
          </div>
        </template>

        <!-- A street edited on its own. -->
        <div
          v-else
          :key="row.key"
          class="edge-row edge-row--click"
          :data-lit="scenarioStore.hoveredSet.has(row.key)"
          title="Zoom to this street"
          @click="focus([row.key])"
          @mouseenter="scenarioStore.hover({ keys: [row.key], dir: row.dir })"
          @mouseleave="scenarioStore.hover(null)"
        >
          <span class="edge-row__badge">{{ edgeBadge(row.action) }}</span>
          <span class="edge-row__name">{{ row.name }}</span>
          <span class="edge-row__dir">{{ DIR_GLYPH[row.dir] }}</span>
          <button
            class="edge-row__remove"
            title="Remove this modification"
            @click.stop="scenarioStore.remove(row.key)"
          >
            <BcIcon name="x" />
          </button>

          <div v-if="rowFor(row.key)" class="edge-row__meta">
            <span class="edge-row__bar">
              <span
                class="edge-row__bar-fill"
                :style="{
                  width: barWidth(rowFor(row.key)!.value),
                  background: rowFor(row.key)!.color
                }"
              ></span>
            </span>
            <span class="edge-row__delta">{{ deltaText(rowFor(row.key)!.value) }}</span>
          </div>
        </div>
      </template>

      <p v-if="scenarioStore.count === 0" class="bc-empty edge-empty">
        Click a street on the map to close it or set a speed limit. ⇧-click adds streets to the
        selection.
      </p>
    </section>

    <!-- The tool zone: the tabs and the body of the active one -->
    <section
      class="zone zone--tool"
      :data-dim="dimmed === 'tool'"
      :data-lit="dimmed === 'scenario'"
      @pointerdown.capture="light('tool')"
      @focusin="light('tool')"
    >
      <BcTabs v-model="scenarioStore.activeTab" :tabs="tabs" />

      <RoutingTab v-if="scenarioStore.activeTab === 'routing'" />
      <p v-else-if="trafficStore.area" class="bc-empty dock-section">
        Waste collection runs on Lausanne only, it needs the bin data. Set the area back to Lausanne
        to use it.
      </p>
      <CvrpTab v-else @hover-route="(id) => emit('hover-route', id)" />

      <!-- Where the diverted traffic ended up. These streets were not touched,
           they are what the result says, so they belong to the tool. -->
      <div v-if="absorbers.length" class="dock-section absorb">
        <div class="bc-micro absorb-head">Where the traffic went · top 3</div>
        <div
          v-for="row in absorbers"
          :key="row.key"
          class="edge-row edge-row--absorb edge-row--click"
          :data-lit="scenarioStore.hoveredSet.has(row.key)"
          title="Zoom to this street"
          @click="focus([row.key])"
          @mouseenter="scenarioStore.hover({ keys: [row.key], dir: 'both' })"
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
      </div>
    </section>
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

/*
 * The map draws one zone at a time. The other one steps back to 40 %, the same
 * fade a stale result gets on the map, and comes back on hover so it stays
 * readable. It is never disabled: a click both lights it and does its job.
 */
.zone {
  position: relative;
  transition: opacity var(--bc-t);
}

.zone--tool {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.zone[data-dim='true'] {
  opacity: 0.4;
}

.zone[data-dim='true']:hover,
.zone[data-dim='true']:focus-within {
  opacity: 0.7;
}

.zone[data-lit='true']::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 2px;
  background: var(--bc-ink);
}

.tools {
  margin-bottom: 12px;
}

.tools__note {
  margin: 6px 0 0;
}

.head-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.focus-btn {
  display: flex;
  align-items: center;
  background: none;
  border: 0;
  padding: 0;
  color: var(--bc-grey);
  cursor: pointer;
  transition: color var(--bc-t);
}

.focus-btn:hover {
  color: var(--bc-ink);
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

.area-name {
  font-size: var(--bc-fs-body);
  padding: 4px 0 0;
}

.area-note {
  margin: 6px 0 0;
}

.area-error {
  margin: 6px 0 0;
  color: var(--bc-danger);
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

.edge-row--click {
  cursor: pointer;
}

.edge-row[data-lit='true'] {
  background: var(--bc-hover);
  box-shadow: -3px 0 0 0 var(--bc-accent);
}

/* the group controls go on their own line, under the name */
.edge-row__group {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
  cursor: default;
}

.group-toggle {
  white-space: nowrap;
}

/* a street inside an open group, stepped in under it */
.edge-row--child {
  grid-template-columns: 1fr 14px;
  padding-left: 12px;
  color: var(--bc-grey);
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

/* last block of the dock, so no rule under it */
.absorb {
  border-bottom: 0;
}

.absorb-head {
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
