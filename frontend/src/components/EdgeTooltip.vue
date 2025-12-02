<script setup lang="ts">
import type { EdgeTooltipData } from '@/composables/useDeckGLTrafficAnalysis'

defineProps<{
  data: EdgeTooltipData | null
}>()

// Format highway type for display
function formatHighway(highway?: string): string {
  if (!highway) return 'Unknown'
  return highway.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())
}

// Format length in meters/km
function formatLength(meters?: number): string {
  if (meters === undefined) return '-'
  if (meters < 1000) return `${Math.round(meters)} m`
  return `${(meters / 1000).toFixed(2)} km`
}

// Format travel time in seconds/minutes
function formatTime(seconds?: number): string {
  if (seconds === undefined) return '-'
  if (seconds < 60) return `${Math.round(seconds)} s`
  return `${(seconds / 60).toFixed(1)} min`
}

// Format frequency as percentage
function formatFrequency(freq?: number): string {
  if (freq === undefined) return '-'
  return `${(freq * 100).toFixed(1)}%`
}

// Format CO2 in grams
function formatCO2(grams?: number): string {
  if (grams === undefined || grams === 0) return '-'
  if (Math.abs(grams) < 1000) return `${grams.toFixed(1)} g`
  return `${(grams / 1000).toFixed(2)} kg`
}

// Format delta with sign
function formatDelta(value?: number): string {
  if (value === undefined || value === 0) return '-'
  const sign = value > 0 ? '+' : ''
  return `${sign}${value}`
}

// Format CO2 delta with sign
function formatCO2Delta(grams?: number): string {
  if (grams === undefined || grams === 0) return '-'
  const sign = grams > 0 ? '+' : ''
  if (Math.abs(grams) < 1000) return `${sign}${grams.toFixed(1)} g`
  return `${sign}${(grams / 1000).toFixed(2)} kg`
}
</script>

<template>
  <div
    v-if="data"
    class="edge-tooltip"
    :style="{
      left: `${data.x + 15}px`,
      top: `${data.y + 15}px`
    }"
  >
    <!-- Edge Name -->
    <div class="tooltip-header">
      {{ data.name }}
    </div>

    <!-- Basic Edge Info -->
    <div class="tooltip-section">
      <div class="tooltip-row">
        <span class="label">Type:</span>
        <span class="value">{{ formatHighway(data.highway) }}</span>
      </div>
      <div v-if="data.length" class="tooltip-row">
        <span class="label">Length:</span>
        <span class="value">{{ formatLength(data.length) }}</span>
      </div>
      <div v-if="data.travel_time" class="tooltip-row">
        <span class="label">Travel time:</span>
        <span class="value">{{ formatTime(data.travel_time) }}</span>
      </div>
      <div v-if="data.speed_kph" class="tooltip-row">
        <span class="label">Speed:</span>
        <span class="value">{{ data.speed_kph }} km/h</span>
      </div>
    </div>

    <!-- Route Stats (if available) -->
    <div
      v-if="data.frequency !== undefined || data.count !== undefined"
      class="tooltip-section route-stats"
    >
      <div class="section-title">Route Statistics</div>
      <div v-if="data.count !== undefined" class="tooltip-row">
        <span class="label">Usage count:</span>
        <span class="value">{{ data.count }}</span>
      </div>
      <div v-if="data.frequency !== undefined" class="tooltip-row">
        <span class="label">Frequency:</span>
        <span class="value">{{ formatFrequency(data.frequency) }}</span>
      </div>
      <div v-if="data.delta_count !== undefined && data.delta_count !== 0" class="tooltip-row">
        <span class="label">Usage change:</span>
        <span
          class="value"
          :class="{ positive: data.delta_count > 0, negative: data.delta_count < 0 }"
        >
          {{ formatDelta(data.delta_count) }}
        </span>
      </div>
    </div>

    <!-- CO2 Stats (if available) -->
    <div
      v-if="data.co2_per_use || data.co2_total || data.co2_delta"
      class="tooltip-section co2-stats"
    >
      <div class="section-title">CO₂ Emissions</div>
      <div v-if="data.co2_per_use" class="tooltip-row">
        <span class="label">Per use:</span>
        <span class="value">{{ formatCO2(data.co2_per_use) }}</span>
      </div>
      <div v-if="data.co2_total" class="tooltip-row">
        <span class="label">Total:</span>
        <span class="value">{{ formatCO2(data.co2_total) }}</span>
      </div>
      <div v-if="data.co2_delta && data.co2_delta !== 0" class="tooltip-row">
        <span class="label">Change:</span>
        <span class="value" :class="{ positive: data.co2_delta > 0, negative: data.co2_delta < 0 }">
          {{ formatCO2Delta(data.co2_delta) }}
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.edge-tooltip {
  position: fixed;
  z-index: 1001;
  background: rgba(255, 255, 255, 0.98);
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 12px;
  min-width: 180px;
  max-width: 280px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  font-size: 13px;
  pointer-events: none;
}

.tooltip-header {
  font-weight: 600;
  font-size: 14px;
  color: #1a1a1a;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid #eee;
  word-break: break-word;
}

.tooltip-section {
  margin-bottom: 8px;
}

.tooltip-section:last-child {
  margin-bottom: 0;
}

.section-title {
  font-size: 11px;
  font-weight: 600;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 4px;
  margin-top: 4px;
}

.tooltip-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 2px 0;
}

.label {
  color: #666;
  font-size: 12px;
}

.value {
  font-weight: 500;
  color: #1a1a1a;
  text-align: right;
}

.value.positive {
  color: #dc2626;
}

.value.negative {
  color: #16a34a;
}

.route-stats {
  background: #f8f9fa;
  margin: 8px -12px;
  padding: 8px 12px;
}

.co2-stats {
  background: #fef3c7;
  margin: 8px -12px -12px -12px;
  padding: 8px 12px;
  border-radius: 0 0 7px 7px;
}
</style>
