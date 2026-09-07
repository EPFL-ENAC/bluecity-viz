<script setup lang="ts">
import EdgeHoverCard, { type HoverCardData } from '@/components/map/EdgeHoverCard.vue'
import EdgePopover from '@/components/map/EdgePopover.vue'
import EditChip from '@/components/map/EditChip.vue'
import ModeToggle from '@/components/map/ModeToggle.vue'
import RouteHoverCard, { type RouteCardData } from '@/components/map/RouteHoverCard.vue'
import { useGraphEdges } from '@/composables/useGraphEdges'
import { useGraphOverlay, type EdgeHover, type RouteHover } from '@/composables/useGraphOverlay'
import { useScenarioStore, type ScenarioAction, type ScenarioDir } from '@/stores/scenario'
import { useCVRPStore } from '@/stores/cvrp'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { routeSummaries } from '@/utils/cvrpSource'
import { buildGraphSource, type GraphSource } from '@/utils/graphSource'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { computed, inject, onUnmounted, ref, shallowRef, watch, type Ref } from 'vue'

// Everything the map draws on top of the line-free basemap: the street graph,
// the routing result, the waste collection routes, the ink modifications and
// the pointer.

const scenarioStore = useScenarioStore()
const trafficStore = useTrafficAnalysisStore()
const cvrpStore = useCVRPStore()
const { edges, loadGraphEdges } = useGraphEdges()

const mapComponentRef = inject<Ref<{ map?: MapLibreMap } | undefined>>('mapRef')
const map = computed(() => mapComponentRef?.value?.map)

const graph = shallowRef<GraphSource | null>(null)
watch(
  edges,
  (list) => {
    if (list.length === 0) return
    const source = buildGraphSource(list)
    graph.value = source
    // The scenario needs the streets to expand 'both' and to fold a one-way.
    scenarioStore.setStreets(source.streets)
  },
  { immediate: true }
)

const hoverCard = ref<InstanceType<typeof EdgeHoverCard> | null>(null)
const hoverData = ref<HoverCardData | null>(null)

/**
 * The numbers for one street: both directed edges summed, as the design asks.
 * The store already sums them once per result, so the card just looks the
 * street up instead of scanning every edge on every move of the mouse.
 */
const totalsByStreet = computed(() => {
  const rows = trafficStore.resultTotals
  const map = new Map<string, (typeof rows)[number]>()
  for (const row of rows) map.set(row.key, row)
  return map
})

function usageFor(key: string) {
  const row = totalsByStreet.value.get(key)
  if (!row) return null
  return {
    vehicles: row.count,
    delta: row.delta_count,
    deltaRelative: row.delta_relative || undefined,
    co2Delta: row.co2_delta || undefined
  }
}

function onHover(hover: EdgeHover | null, point: { x: number; y: number }) {
  if (!hover) {
    hoverData.value = null
    return
  }

  const usage = usageFor(hover.key)
  hoverData.value = {
    name: hover.name,
    highway: hover.highway,
    speed: hover.speed,
    oneway: hover.oneway,
    vehicles: usage?.vehicles,
    delta: usage?.delta,
    deltaRelative: usage?.deltaRelative,
    co2Delta: usage?.co2Delta,
    deltaColor: usage?.delta !== undefined ? deltaColor(usage.delta) : undefined
  }
  hoverCard.value?.move(point.x, point.y)
}

function deltaColor(delta: number): string | undefined {
  const scale = trafficStore.colorScale
  return scale ? scale(delta) : undefined
}

// The popover, opened by a click while in edit mode.
const popover = ref<{ x: number; y: number; key: string; dir: ScenarioDir } | null>(null)

function onPick(key: string, dir: ScenarioDir, point: { x: number; y: number }) {
  popover.value = { key, dir, x: point.x, y: point.y }
}

// Per vehicle totals, so the card can say how far it drives and how many trips.
const routeTotals = computed(() =>
  cvrpStore.lastResult ? routeSummaries(cvrpStore.lastResult.route_segments) : []
)

const routeCard = ref<InstanceType<typeof RouteHoverCard> | null>(null)
const routeData = shallowRef<RouteCardData | null>(null)

function onRoute(route: RouteHover | null, point: { x: number; y: number }) {
  if (!route) {
    routeData.value = null
    return
  }
  const totals = routeTotals.value.find((row) => row.route_id === route.route_id)
  routeData.value = {
    ...route,
    wasteType: cvrpStore.wasteType,
    distance_m: totals?.distance_m,
    trips: totals?.trips
  }
  routeCard.value?.move(point.x, point.y)
}

const overlay = useGraphOverlay(map as Ref<MapLibreMap | undefined>, graph, {
  onHover,
  onPick,
  onRoute
})

watch(
  map,
  (instance, previous) => {
    if (previous) overlay.detach(previous)
    if (instance) overlay.attach(instance)
  },
  { immediate: true }
)

// Leaving edit mode closes the popover with it.
watch(
  () => scenarioStore.editMode,
  (on) => {
    if (!on) popover.value = null
  }
)

const popoverStreet = computed(() => {
  const open = popover.value
  if (!open) return null
  const street = graph.value?.streets.get(open.key)
  if (!street) return null

  return {
    name: street.name || `Edge ${street.lo}→${street.hi}`,
    edges: street.oneway ? 1 : 2,
    speed: street.speed,
    oneway: street.oneway,
    toForward: destination(street.hi, street.name),
    toBackward: destination(street.lo, street.name)
  }
})

/** Where a direction leads: the first other street name at the far node. */
function destination(node: number, own: string): string {
  const names = graph.value?.nodeStreets.get(node) ?? []
  const other = names.find((name) => name !== own)
  return other ? `To ${other}` : ''
}

const currentAction = computed<ScenarioAction | null>(
  () => (popover.value && scenarioStore.get(popover.value.key)?.action) || null
)

function setAction(action: ScenarioAction) {
  const open = popover.value
  if (!open) return
  const street = graph.value?.streets.get(open.key)
  scenarioStore.set(open.key, {
    action,
    dir: open.dir,
    name: street?.name || `Edge ${open.key}`
  })
}

function setDir(dir: ScenarioDir) {
  const open = popover.value
  if (!open) return
  popover.value = { ...open, dir }
  scenarioStore.select({ key: open.key, dir })
  // move an existing modification onto the direction the user just picked
  if (scenarioStore.get(open.key)) scenarioStore.setDir(open.key, dir)
}

function reset() {
  const open = popover.value
  if (!open) return
  scenarioStore.remove(open.key)
}

void loadGraphEdges()

defineExpose({ hoverRoute: overlay.hoverRoute })

onUnmounted(() => {
  const instance = map.value
  if (instance) {
    overlay.detach(instance)
    overlay.unmount()
  }
})
</script>

<template>
  <div class="graph-overlay">
    <EditChip v-if="scenarioStore.editMode" />
    <ModeToggle v-else />

    <!-- The popover sits where the cursor is, so a card would land on top of it. -->
    <EdgeHoverCard ref="hoverCard" :data="popover ? null : hoverData" />
    <RouteHoverCard ref="routeCard" :data="popover ? null : routeData" />

    <EdgePopover
      v-if="popover && popoverStreet"
      :x="popover.x"
      :y="popover.y"
      :name="popoverStreet.name"
      :edges="popoverStreet.edges"
      :speed="popoverStreet.speed"
      :dir="popover.dir"
      :action="currentAction"
      :to-forward="popoverStreet.toForward"
      :to-backward="popoverStreet.toBackward"
      :oneway="popoverStreet.oneway"
      @dir="setDir"
      @action="setAction"
      @reset="reset"
    />
  </div>
</template>

<style scoped>
.graph-overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

/* the dock covers the right edge of the map, keep the popover clear of it */
.graph-overlay.is-docked {
  right: var(--bc-dock-w);
}

.graph-overlay :deep(.popover) {
  pointer-events: auto;
}
</style>
