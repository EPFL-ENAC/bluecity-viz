<script setup lang="ts">
import { classLabel } from '@/utils/graphSource'
import { computed, ref } from 'vue'

export interface HoverCardData {
  name: string
  highway?: string
  speed?: number
  oneway: boolean
  /** the value of the layer on the map, both directions summed */
  stat?: {
    label: string
    value: string
    /** the ramp colour of the value, so the card matches the map */
    color?: string
  }
}

const props = defineProps<{ data: HoverCardData | null }>()

const root = ref<HTMLElement | null>(null)

// The cursor moves at 60 Hz. Writing x and y into a prop would re-render the
// card every frame, so the parent calls move() and we go straight to the style.
const GAP = 15

function move(x: number, y: number): void {
  const el = root.value
  if (!el) return

  // Near the right or the bottom edge of the stage, put the card on the other
  // side of the cursor instead of letting it run under the dock.
  const box = el.offsetParent as HTMLElement | null
  const width = box ? box.clientWidth : window.innerWidth
  const height = box ? box.clientHeight : window.innerHeight

  let left = x + GAP
  let top = y + GAP
  if (left + el.offsetWidth > width) left = x - GAP - el.offsetWidth
  if (top + el.offsetHeight > height) top = y - GAP - el.offsetHeight

  el.style.transform = `translate3d(${Math.max(0, left)}px, ${Math.max(0, top)}px, 0)`
}

defineExpose({ move })

const meta = computed(() => {
  const data = props.data
  if (!data) return ''
  const parts = [classLabel(data.highway)]
  if (data.speed) parts.push(`${Math.round(data.speed)} KM/H`)
  parts.push(data.oneway ? '→ 1 EDGE' : '↔ 2 EDGES')
  return parts.join(' · ')
})
</script>

<template>
  <div v-show="props.data" ref="root" class="hover-card">
    <template v-if="props.data">
      <div class="hover-card__head">
        <div class="hover-card__name">{{ props.data.name }}</div>
        <div class="hover-card__meta">{{ meta }}</div>
      </div>

      <div v-if="props.data.stat" class="hover-card__stats">
        <span class="hover-card__label">{{ props.data.stat.label }}</span>
        <span class="hover-card__value">
          <!-- The ramp colour as a swatch, not on the text: the middle of a
               diverging ramp is a pale yellow you cannot read on paper. -->
          <span
            v-if="props.data.stat.color"
            class="hover-card__swatch"
            :style="{ background: props.data.stat.color }"
          ></span>
          {{ props.data.stat.value }}
        </span>
      </div>

      <div class="hover-card__foot bc-micro">
        Click · edit &nbsp;·&nbsp; ⇧ click · add to selection
      </div>
    </template>
  </div>
</template>

<style scoped>
.hover-card {
  position: absolute;
  top: 0;
  left: 0;
  z-index: 1001;
  width: 232px;
  background: var(--bc-panel);
  border: 1px solid var(--bc-ink);
  pointer-events: none;
  will-change: transform;
}

.hover-card__head {
  padding: 10px 12px 8px;
  border-bottom: 1px solid var(--bc-line);
}

.hover-card__name {
  font-size: 14px;
  letter-spacing: -0.01em;
}

.hover-card__meta {
  margin-top: 2px;
  font-family: var(--bc-font-mono);
  font-size: var(--bc-fs-micro);
  letter-spacing: 0.04em;
  color: var(--bc-grey);
}

.hover-card__stats {
  padding: 8px 12px 10px;
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 3px 12px;
  font-size: 12.5px;
  font-variant-numeric: tabular-nums;
}

.hover-card__label {
  color: var(--bc-grey);
}

.hover-card__value {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
}

.hover-card__swatch {
  width: 8px;
  height: 8px;
  flex: none;
}

.hover-card__foot {
  padding: 7px 12px;
  border-top: 1px solid var(--bc-line);
  color: var(--bc-accent);
}
</style>
