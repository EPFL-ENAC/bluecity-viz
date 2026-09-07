<script setup lang="ts">
import { classLabel } from '@/utils/graphSource'
import { computed, ref } from 'vue'

export interface HoverCardData {
  name: string
  highway?: string
  speed?: number
  oneway: boolean
  /** vehicles a day on the street, both directions summed */
  vehicles?: number
  delta?: number
  deltaRelative?: number
  co2Delta?: number
  /** the ramp colour of the change, so the number matches the map */
  deltaColor?: string
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
  if (data.speed) parts.push(`${data.speed} KM/H`)
  parts.push(data.oneway ? '→ 1 EDGE' : '↔ 2 EDGES')
  return parts.join(' · ')
})

function number(value?: number): string {
  if (value === undefined || value === null) return '—'
  // fr-CH groups with a narrow no-break space; use a plain one
  return Math.round(value)
    .toLocaleString('fr-CH')
    .replace(/[\u202f\u00a0\u2009]/g, ' ')
}

const change = computed(() => {
  const data = props.data
  if (!data || data.delta === undefined) return null
  const sign = data.delta > 0 ? '+' : ''
  const relative =
    data.deltaRelative === undefined ? '' : ` · ${sign}${data.deltaRelative.toFixed(1)}%`
  return `${sign}${number(data.delta)}${relative}`
})

const co2 = computed(() => {
  const value = props.data?.co2Delta
  if (value === undefined) return null
  const sign = value > 0 ? '+' : ''
  if (Math.abs(value) < 1000) return `${sign}${value.toFixed(0)} g`
  return `${sign}${(value / 1000).toFixed(1)} kg`
})
</script>

<template>
  <div v-show="props.data" ref="root" class="hover-card">
    <template v-if="props.data">
      <div class="hover-card__head">
        <div class="hover-card__name">{{ props.data.name }}</div>
        <div class="hover-card__meta">{{ meta }}</div>
      </div>

      <div v-if="props.data.vehicles !== undefined || change" class="hover-card__stats">
        <template v-if="props.data.vehicles !== undefined">
          <span class="hover-card__label">Vehicles / day</span>
          <span class="hover-card__value">{{ number(props.data.vehicles) }}</span>
        </template>
        <template v-if="change">
          <span class="hover-card__label">Change</span>
          <span class="hover-card__value" :style="{ color: props.data.deltaColor }">
            {{ change }}
          </span>
        </template>
        <template v-if="co2">
          <span class="hover-card__label">CO₂ change</span>
          <span class="hover-card__value">{{ co2 }}</span>
        </template>
      </div>

      <div class="hover-card__foot bc-micro">
        Click · both directions &nbsp;·&nbsp; ⇧ click · this lane
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
  text-align: right;
}

.hover-card__foot {
  padding: 7px 12px;
  border-top: 1px solid var(--bc-line);
  color: var(--bc-accent);
}
</style>
