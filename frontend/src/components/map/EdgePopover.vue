<script setup lang="ts">
import type { ScenarioAction, ScenarioDir } from '@/stores/scenario'
import { nextTick, onMounted, ref, watch } from 'vue'

/**
 * The on-map editor. It replaces click cycling: the user says which direction
 * and which action, instead of clicking four times to reach 10 km/h.
 */
const props = defineProps<{
  x: number
  y: number
  name: string
  edges: number
  speed?: number
  dir: ScenarioDir
  action: ScenarioAction | null
  /** where each direction leads, for the row labels */
  toForward?: string
  toBackward?: string
  oneway: boolean
}>()

const emit = defineEmits<{
  (event: 'dir', value: ScenarioDir): void
  (event: 'action', value: ScenarioAction): void
  (event: 'reset'): void
}>()

const ACTIONS: ScenarioAction[] = ['remove', '50', '30', '10']

function actionLabel(action: ScenarioAction) {
  return action === 'remove' ? '×' : action
}

// The click can land near an edge of the map stage, so keep the box inside it.
const MARGIN = 8
const root = ref<HTMLElement | null>(null)
const at = ref({ left: props.x, top: props.y })

function place(): void {
  const el = root.value
  if (!el) return
  const box = el.offsetParent as HTMLElement | null
  const width = box ? box.clientWidth : window.innerWidth
  const height = box ? box.clientHeight : window.innerHeight
  at.value = {
    left: Math.max(MARGIN, Math.min(props.x, width - el.offsetWidth - MARGIN)),
    top: Math.max(MARGIN, Math.min(props.y, height - el.offsetHeight - MARGIN))
  }
}

onMounted(place)
watch(
  () => [props.x, props.y, props.dir, props.name],
  () => void nextTick(place)
)
</script>

<template>
  <div ref="root" class="popover" :style="{ left: `${at.left}px`, top: `${at.top}px` }">
    <div class="popover__head">
      <span class="popover__name">{{ props.name }}</span>
      <span class="popover__meta">
        {{ props.edges }} EDGES<template v-if="props.speed"> · {{ props.speed }} KM/H</template>
      </span>
    </div>

    <div v-if="!props.oneway" class="popover__row">
      <span class="popover__label">Direction</span>
      <button
        class="seg"
        :data-on="props.dir === 'both'"
        type="button"
        @click="emit('dir', 'both')"
      >
        <span class="seg__glyph">↔</span>
        <span class="seg__text">Both</span>
      </button>
      <button class="seg" :data-on="props.dir === 'fwd'" type="button" @click="emit('dir', 'fwd')">
        <span class="seg__glyph">→</span>
        <span class="seg__text">{{ props.toForward || 'forward' }}</span>
      </button>
      <button class="seg" :data-on="props.dir === 'bwd'" type="button" @click="emit('dir', 'bwd')">
        <span class="seg__glyph">←</span>
        <span class="seg__text">{{ props.toBackward || 'backward' }}</span>
      </button>
    </div>

    <div class="popover__row popover__row--actions">
      <span class="popover__label">Action</span>
      <button
        v-for="option in ACTIONS"
        :key="option"
        class="action"
        :data-on="props.action === option"
        type="button"
        @click="emit('action', option)"
      >
        {{ actionLabel(option) }}
      </button>
      <button class="reset bc-micro" type="button" @click="emit('reset')">Reset</button>
    </div>
  </div>
</template>

<style scoped>
.popover {
  position: absolute;
  z-index: 4;
  background: var(--bc-panel);
  border: 1px solid var(--bc-ink);
  display: flex;
  flex-direction: column;
}

.popover__head {
  padding: 8px 12px 6px;
  display: flex;
  align-items: baseline;
  gap: 10px;
  border-bottom: 1px solid var(--bc-line);
}

.popover__name {
  font-size: 13px;
}

.popover__meta {
  font-family: var(--bc-font-mono);
  font-size: var(--bc-fs-micro);
  letter-spacing: 0.04em;
  color: var(--bc-grey);
  white-space: nowrap;
}

.popover__row {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 8px 0;
}

.popover__row--actions {
  padding: 6px 8px 8px;
}

.popover__label {
  font-family: var(--bc-font-mono);
  font-size: 9.5px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--bc-grey);
  width: 56px;
  flex: none;
}

.seg {
  height: 28px;
  padding: 0 9px;
  display: flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--bc-ink);
  box-sizing: border-box;
  background: transparent;
  color: var(--bc-ink);
  cursor: pointer;
  font-size: 12px;
  font-family: inherit;
  white-space: nowrap;
}

.seg[data-on='true'],
.action[data-on='true'] {
  background: var(--bc-ink);
  color: var(--bc-ground);
}

.seg__glyph {
  font-weight: 700;
}

.seg__text {
  font-family: var(--bc-font-mono);
  font-size: 9.5px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  max-width: 88px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.action {
  width: 32px;
  height: 28px;
  display: grid;
  place-items: center;
  font-family: var(--bc-font-mono);
  font-size: 11px;
  font-weight: 700;
  border: 1.5px solid var(--bc-ink);
  box-sizing: border-box;
  background: transparent;
  color: var(--bc-ink);
  cursor: pointer;
}

.reset {
  margin-left: 6px;
  background: none;
  border: 0;
  cursor: pointer;
  color: var(--bc-grey);
}

.seg:focus-visible,
.action:focus-visible,
.reset:focus-visible {
  outline: 2px solid var(--bc-accent);
  outline-offset: 2px;
}
</style>
