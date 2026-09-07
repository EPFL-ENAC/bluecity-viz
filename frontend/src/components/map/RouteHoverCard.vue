<script setup lang="ts">
/**
 * What the vehicle under the cursor is carrying.
 *
 * Same shape as the edge card, with the vehicle hue as the only colour: the
 * hue is the identity of the route, the numbers stay ink.
 */
import { computed, ref } from 'vue'

export interface RouteCardData {
  route_id: number
  trip_id: number
  load_kg: number
  color: string
  wasteType: string
  /** how far this vehicle drives in total, metres */
  distance_m?: number
  /** how many trips it makes (the solver gives no stop count) */
  trips?: number
}

const props = defineProps<{ data: RouteCardData | null }>()

const root = ref<HTMLElement | null>(null)
const GAP = 15

function move(x: number, y: number): void {
  const el = root.value
  if (!el) return
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
  return `TRIP ${data.trip_id + 1} · ${data.wasteType}`
})

function number(value?: number): string {
  if (value === undefined) return '—'
  return Math.round(value)
    .toLocaleString('fr-CH')
    .replace(/[\u202f\u00a0\u2009]/g, ' ')
}
</script>

<template>
  <div v-show="props.data" ref="root" class="route-card">
    <template v-if="props.data">
      <div class="route-card__head">
        <span class="route-card__hue" :style="{ background: props.data.color }"></span>
        <div>
          <div class="route-card__name">Vehicle {{ props.data.route_id + 1 }}</div>
          <div class="route-card__meta">{{ meta }}</div>
        </div>
      </div>

      <div class="route-card__stats">
        <span class="route-card__label">Load</span>
        <span class="route-card__value">{{ number(props.data.load_kg) }} kg</span>
        <span class="route-card__label">Trips</span>
        <span class="route-card__value">{{ props.data.trips ?? '—' }}</span>
        <span class="route-card__label">Distance</span>
        <span class="route-card__value">
          {{ props.data.distance_m === undefined ? '—' : (props.data.distance_m / 1000).toFixed(1) }}
          km
        </span>
      </div>
    </template>
  </div>
</template>

<style scoped>
.route-card {
  position: absolute;
  top: 0;
  left: 0;
  z-index: 1001;
  width: 200px;
  background: var(--bc-panel);
  border: 1px solid var(--bc-ink);
  pointer-events: none;
  will-change: transform;
}

.route-card__head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px 8px;
  border-bottom: 1px solid var(--bc-line);
}

.route-card__hue {
  width: 16px;
  height: 3px;
  flex: none;
}

.route-card__name {
  font-size: 14px;
  letter-spacing: -0.01em;
}

.route-card__meta {
  margin-top: 2px;
  font-family: var(--bc-font-mono);
  font-size: var(--bc-fs-micro);
  letter-spacing: 0.04em;
  color: var(--bc-grey);
}

.route-card__stats {
  padding: 8px 12px 10px;
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 3px 12px;
  font-size: 12.5px;
  font-variant-numeric: tabular-nums;
}

.route-card__label {
  color: var(--bc-grey);
}

.route-card__value {
  text-align: right;
}
</style>
