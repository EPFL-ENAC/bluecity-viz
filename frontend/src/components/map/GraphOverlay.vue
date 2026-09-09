<script setup lang="ts">
import EdgeHoverCard, { type HoverCardData } from '@/components/map/EdgeHoverCard.vue'
import EdgePopover from '@/components/map/EdgePopover.vue'
import RouteHoverCard, { type RouteCardData } from '@/components/map/RouteHoverCard.vue'
import { useGraphEdges } from '@/composables/useGraphEdges'
import { useGraphOverlay, type EdgeHover, type RouteHover } from '@/composables/useGraphOverlay'
import { useMapView } from '@/composables/useMapView'
import { useSelectTools } from '@/composables/useSelectTools'
import { useCVRPStore } from '@/stores/cvrp'
import {
  useScenarioStore,
  type ScenarioAction,
  type ScenarioDir,
  type StreetMod
} from '@/stores/scenario'
import { useTrafficAnalysisStore } from '@/stores/trafficAnalysis'
import { collectPlaces } from '@/utils/areaName'
import { routeSummaries } from '@/utils/cvrpSource'
import { buildGraphSource, type GraphSource } from '@/utils/graphSource'
import { groupName, type NamedLine } from '@/utils/groupName'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { computed, inject, onUnmounted, ref, shallowRef, watch, type Ref } from 'vue'

// Everything the map draws on top of the line-free basemap: the street graph,
// the routing result, the waste collection routes, the ink modifications and
// the pointer.

const scenarioStore = useScenarioStore()
const trafficStore = useTrafficAnalysisStore()
const cvrpStore = useCVRPStore()
const { edges, showArea } = useGraphEdges()
const { shown } = useMapView()

const mapComponentRef = inject<Ref<{ map?: MapLibreMap } | undefined>>('mapRef')
const map = computed(() => mapComponentRef?.value?.map)

const graph = shallowRef<GraphSource | null>(null)
watch(
  edges,
  (list) => {
    if (list.length === 0) {
      // Another area, its network not here yet. Drawing the old streets would
      // let the user click a street that is not in the new graph.
      graph.value = null
      scenarioStore.setStreets(new Map())
      return
    }
    const source = buildGraphSource(list)
    graph.value = source
    // The scenario needs the streets to expand 'both' and to fold a one-way.
    scenarioStore.setStreets(source.streets)
  },
  { immediate: true }
)

// The circle and the streets under it are one thing, so they read one key.
// The default city comes from a static file, an area the user drew is built
// by the server and then fetched. Both are cached, so going back is instant.
watch(
  () => trafficStore.graphKey,
  (key) => {
    void showArea(
      key,
      () => trafficStore.ensureArea(),
      () => trafficStore.forgetAreaId()
    )
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
  // The card reads the map: no routing colours on screen, no routing numbers.
  if (shown.value !== 'routing') return null
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

// Where the popover sits. What it edits is the selection in the store.
const popover = ref<{ x: number; y: number } | null>(null)
const popoverRef = ref<InstanceType<typeof EdgePopover> | null>(null)

function onPick(point: { x: number; y: number }) {
  popover.value = { x: point.x, y: point.y }
}

/**
 * Anything the user touches outside the popover closes it.
 *
 * Two exceptions. Inside the popover, of course. And on the map canvas, where
 * the click handler decides: it may be a click on another street, which must
 * move the selection, not drop it.
 */
function onDocumentPointerDown(event: PointerEvent): void {
  const target = event.target as Node | null
  if (!target) return
  const root = popoverRef.value?.$el as HTMLElement | undefined
  if (root && root.contains(target)) return
  if (map.value?.getCanvasContainer().contains(target)) return
  scenarioStore.select(null)
}

watch(popover, (open) => {
  if (open) document.addEventListener('pointerdown', onDocumentPointerDown, true)
  else document.removeEventListener('pointerdown', onDocumentPointerDown, true)
})

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

// The lasso and the brush. They only fill the selection, then the popover
// opens where the stroke ended and asks what to do with it.
const tools = useSelectTools(map as Ref<MapLibreMap | undefined>, overlay.streetsInBox, {
  onDone: onPick
})

watch(
  map,
  (instance, previous) => {
    if (previous) {
      overlay.detach(previous)
      tools.detach(previous)
    }
    if (instance) {
      overlay.attach(instance)
      tools.attach(instance)
    }
  },
  { immediate: true }
)

/** The lasso polygon, ready for the SVG points attribute. */
const lassoPoints = computed(() => {
  const shape = tools.shape.value
  if (shape?.kind !== 'lasso') return ''
  return shape.points.map((point) => point.join(',')).join(' ')
})

const brush = computed(() => (tools.shape.value?.kind === 'brush' ? tools.shape.value : null))

const brushTrail = computed(() => {
  const trail = brush.value?.trail ?? []
  return trail.map((point) => point.join(',')).join(' ')
})

// Dropping the selection (Esc, or a click on empty map) closes the popover.
watch(
  () => scenarioStore.selected,
  (edge) => {
    if (!edge) popover.value = null
  }
)

// Closing the workbench leaves the graph on the map but stops pointing at it,
// so the cards go with it.
watch(
  () => scenarioStore.isOpen,
  (open) => {
    if (open) return
    hoverData.value = null
    routeData.value = null
    popover.value = null
  }
)

/** The streets the popover edits, in selection order. */
const selectedStreets = computed(() => {
  const keys = scenarioStore.selected?.keys ?? []
  const source = graph.value
  if (!source) return []
  return keys.map((key) => source.streets.get(key)).filter((street) => !!street)
})

/**
 * What the head and the rows say, for one street or for many.
 *
 * With several streets the name becomes a count, and the two direction labels
 * go away: they name where a single street leads.
 */
const popoverStreet = computed(() => {
  if (!popover.value) return null
  const streets = selectedStreets.value
  if (streets.length === 0) return null

  const one = streets.length === 1 ? streets[0] : null
  return {
    name: one ? one.name || `Edge ${one.lo}→${one.hi}` : `${streets.length} streets`,
    edges: streets.reduce((total, street) => total + (street.oneway ? 1 : 2), 0),
    speed: one ? one.speed : undefined,
    // Nothing to choose when every street runs one way.
    oneway: streets.every((street) => street.oneway),
    toForward: one ? destination(one.hi, one.name) : '',
    toBackward: one ? destination(one.lo, one.name) : ''
  }
})

/** Where a direction leads: the first other street name at the far node. */
function destination(node: number, own: string): string {
  const names = graph.value?.nodeStreets.get(node) ?? []
  const other = names.find((name) => name !== own)
  return other ? `To ${other}` : ''
}

/** The action the buttons show as on, only when every street agrees. */
const currentAction = computed<ScenarioAction | null>(() => {
  const keys = scenarioStore.selected?.keys ?? []
  if (keys.length === 0) return null
  const first = scenarioStore.get(keys[0])?.action ?? null
  if (!first) return null
  return keys.every((key) => scenarioStore.get(key)?.action === first) ? first : null
})

function nameOf(key: string): string {
  return graph.value?.streets.get(key)?.name || `Edge ${key}`
}

/** The shape and the name of each street, for naming a zone. */
function linesOf(keys: string[]): NamedLine[] {
  const source = graph.value
  if (!source) return []

  const lines: NamedLine[] = []
  for (const key of keys) {
    const street = source.streets.get(key)
    const id = street?.fwdId ?? street?.bwdId
    if (id === undefined) continue
    const feature = source.collection.features[id]
    if (!feature) continue
    lines.push({
      name: street?.name ?? '',
      coordinates: feature.geometry.coordinates as [number, number][]
    })
  }
  return lines
}

/**
 * The group a selection belongs to, when it is exactly one whole group.
 *
 * Editing a zone from its badge selects every street of it, and that edit has
 * to keep the name the zone already has instead of making a second one.
 */
function groupOfSelection(keys: string[]): string | undefined {
  for (const group of scenarioStore.groups.values()) {
    if (group.keys.length !== keys.length) continue
    const held = new Set(group.keys)
    if (keys.every((key) => held.has(key))) return group.id
  }
  return undefined
}

/** The name a new zone takes: the place around it, free of any clash. */
function nameGroup(keys: string[]): string {
  const instance = map.value
  const places = instance ? collectPlaces(instance) : []
  return scenarioStore.freeGroupId(groupName(linesOf(keys), places))
}

function setAction(action: ScenarioAction) {
  const selection = scenarioStore.selected
  if (!selection) return
  const dir = selection.dir

  // Several streets edited together become a group, and the dock shows them
  // as one row. Editing a single street takes it out of the group it was in,
  // so a group row never shows two different values.
  const group =
    selection.keys.length > 1
      ? (groupOfSelection(selection.keys) ?? nameGroup(selection.keys))
      : undefined

  scenarioStore.setMany(
    selection.keys.map(
      (key) => [key, { action, dir, name: nameOf(key), group }] as [string, StreetMod]
    )
  )
  // The action is the last word: the popover has nothing left to ask, and the
  // map goes back to panning instead of drawing another stroke.
  scenarioStore.select(null)
  scenarioStore.tool = 'pointer'
}

function setDir(dir: ScenarioDir) {
  const selection = scenarioStore.selected
  if (!selection) return
  scenarioStore.setSelectedDir(dir)
  // move the modifications that already exist onto the direction just picked
  const moved = selection.keys
    .map((key) => {
      const mod = scenarioStore.get(key)
      return mod ? ([key, { ...mod, dir }] as [string, StreetMod]) : null
    })
    .filter((entry) => !!entry)
  scenarioStore.setMany(moved)
}

function reset() {
  const selection = scenarioStore.selected
  if (!selection) return
  scenarioStore.removeMany(selection.keys)
  scenarioStore.select(null)
  scenarioStore.tool = 'pointer'
}

defineExpose({ hoverRoute: overlay.hoverRoute, focus: overlay.focus })

onUnmounted(() => {
  document.removeEventListener('pointerdown', onDocumentPointerDown, true)
  const instance = map.value
  if (instance) {
    tools.detach(instance)
    overlay.detach(instance)
    overlay.unmount()
  }
})
</script>

<template>
  <div class="graph-overlay">
    <!-- The lasso and the brush, in screen pixels: the map holds still under
         a stroke, so there is nothing to reproject. -->
    <svg v-if="tools.shape.value" class="tool-shape">
      <polygon v-if="lassoPoints" :points="lassoPoints" />
      <template v-else-if="brush">
        <polyline v-if="brushTrail" :points="brushTrail" />
        <circle :cx="brush.at[0]" :cy="brush.at[1]" :r="brush.radius" />
      </template>
    </svg>

    <!-- The popover sits where the cursor is, so a card would land on top of it. -->
    <EdgeHoverCard ref="hoverCard" :data="popover ? null : hoverData" />
    <RouteHoverCard ref="routeCard" :data="popover ? null : routeData" />

    <EdgePopover
      v-if="popover && popoverStreet"
      ref="popoverRef"
      :x="popover.x"
      :y="popover.y"
      :name="popoverStreet.name"
      :edges="popoverStreet.edges"
      :speed="popoverStreet.speed"
      :dir="scenarioStore.selected?.dir ?? 'both'"
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

/*
 * The pointer is the only thing that wears the accent, so the lasso and the
 * brush do too: a hairline outline, a wash of blue inside, nothing else.
 */
.tool-shape {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  overflow: visible;
}

.tool-shape polygon {
  fill: var(--bc-accent);
  fill-opacity: 0.08;
  stroke: var(--bc-accent);
  stroke-width: 1;
  stroke-dasharray: 4 3;
}

.tool-shape polyline {
  fill: none;
  stroke: var(--bc-accent);
  stroke-opacity: 0.25;
  stroke-width: 1;
}

.tool-shape circle {
  fill: var(--bc-accent);
  fill-opacity: 0.08;
  stroke: var(--bc-accent);
  stroke-width: 1;
}
</style>
