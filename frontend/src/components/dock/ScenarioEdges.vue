<script setup lang="ts">
import BcIcon from '@/components/ui/BcIcon.vue'
import BcSeg from '@/components/ui/BcSeg.vue'
import BcSlider from '@/components/ui/BcSlider.vue'
import { useDeltaBars } from '@/composables/useDeltaBars'
import { useScenarioStore, type ScenarioDir, type StreetRef } from '@/stores/scenario'
import { ref } from 'vue'

/**
 * The modified edges: how the pointer picks streets, and the list of what was
 * done to them. It lives in the Simulation block of each tool, both tools read
 * the same scenario.
 */

const emit = defineEmits<{
  (event: 'focus', keys: string[], select?: StreetRef): void
}>()

const scenarioStore = useScenarioStore()
const { rowFor, barWidth, deltaText } = useDeltaBars()

/** Fit the map on the modified streets, or on one of them. */
function focus(keys: string[]): void {
  if (keys.length) emit('focus', keys)
}

/**
 * Fit the map on a row and open its popover there.
 *
 * A row and the badge of the same streets do the same thing, so the map is
 * the one place where a modification is edited.
 */
function edit(keys: string[], dir: ScenarioDir): void {
  if (keys.length) emit('focus', keys, { keys, dir })
}

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
  <div class="scenario-edges">
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
          title="Zoom to this zone and edit it"
          @click="edit(row.group.keys, row.group.dir)"
          @mouseenter="scenarioStore.hover({ keys: row.group.keys, dir: row.group.dir })"
          @mouseleave="scenarioStore.hover(null)"
        >
          <span class="edge-row__badge edge-row__badge--group">
            {{ edgeBadge(row.group.action) }}
          </span>
          <span class="edge-row__name">{{ row.group.id }}</span>
          <span class="edge-row__dir">{{ DIR_GLYPH[row.group.dir] }}</span>
          <button
            class="edge-row__expand"
            :title="expanded.has(row.group.id) ? 'Hide the streets' : 'Show the streets'"
            @click.stop="toggleGroup(row.group.id)"
          >
            <span class="edge-row__count">{{ row.group.keys.length }}</span>
            <BcIcon :name="expanded.has(row.group.id) ? 'chevron-down' : 'chevron-right'" />
          </button>
          <button
            class="edge-row__remove"
            title="Remove this zone"
            @click.stop="scenarioStore.removeGroup(row.group.id)"
          >
            <BcIcon name="x" />
          </button>
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
        title="Zoom to this street and edit it"
        @click="edit([row.key], row.dir)"
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
      selection, the lasso and the brush take a whole zone at once.
    </p>
  </div>
</template>

<style scoped>
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

/*
 * A zone reads like a street row. What tells it apart is the heavier badge
 * and the count next to the chevron, not a shape of its own.
 */
.edge-row--group {
  grid-template-columns: 34px 1fr auto auto 14px;
}

.edge-row__badge--group {
  border-width: 2px;
  font-weight: 600;
}

.edge-row__expand {
  display: flex;
  align-items: center;
  gap: 4px;
  background: none;
  border: 0;
  padding: 0;
  color: var(--bc-grey);
  cursor: pointer;
  transition: color var(--bc-t);
}

.edge-row__expand:hover {
  color: var(--bc-ink);
}

.edge-row__count {
  font-family: var(--bc-font-mono);
  font-size: var(--bc-fs-micro);
  font-variant-numeric: tabular-nums;
}

/* a street inside an open group, stepped in under it */
.edge-row--child {
  grid-template-columns: 1fr 14px;
  padding-left: 12px;
  color: var(--bc-grey);
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
</style>
