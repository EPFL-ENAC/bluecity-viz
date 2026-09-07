<script setup lang="ts">
// A slider drawn the Workbench way: a 1px hairline track, 1px ink progress and
// a 1x14px ink thumb. A native input[type=range] keeps it light and accessible.
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    modelValue: number
    min: number
    max: number
    step?: number
    label?: string
    /** formatted value shown on the right of the label row */
    display?: string
  }>(),
  { step: 1, label: undefined, display: undefined }
)

const emit = defineEmits<{ 'update:modelValue': [number] }>()

const pct = computed(() => {
  const span = props.max - props.min
  if (span <= 0) return 0
  return ((props.modelValue - props.min) / span) * 100
})

const onInput = (event: Event) => {
  emit('update:modelValue', Number((event.target as HTMLInputElement).value))
}
</script>

<template>
  <div class="bc-slider">
    <div v-if="label" class="bc-slider__head">
      <span class="bc-slider__label">{{ label }}</span>
      <span class="bc-slider__value">{{ display ?? modelValue }}</span>
    </div>
    <input
      type="range"
      class="bc-slider__input"
      :style="{ '--bc-slider-pct': pct + '%' }"
      :min="min"
      :max="max"
      :step="step"
      :value="modelValue"
      :aria-label="label"
      @input="onInput"
    />
  </div>
</template>

<style scoped>
.bc-slider__head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: var(--bc-fs-body);
}

.bc-slider__label {
  color: var(--bc-grey);
}

.bc-slider__value {
  font-variant-numeric: tabular-nums;
}

.bc-slider__input {
  -webkit-appearance: none;
  appearance: none;
  display: block;
  width: 100%;
  height: 14px;
  margin-top: 4px;
  background: transparent;
  cursor: pointer;
}

/* track: hairline, filled up to the current value */
.bc-slider__input::-webkit-slider-runnable-track {
  height: 14px;
  background:
    linear-gradient(var(--bc-ink), var(--bc-ink)) 0 6px / var(--bc-slider-pct) 1px no-repeat,
    linear-gradient(var(--bc-line), var(--bc-line)) 0 6px / 100% 1px no-repeat;
}

.bc-slider__input::-moz-range-track {
  height: 1px;
  background: var(--bc-line);
}

.bc-slider__input::-moz-range-progress {
  height: 1px;
  background: var(--bc-ink);
}

/* thumb: a 1x14 ink tick */
.bc-slider__input::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 1px;
  height: 14px;
  border: 0;
  border-radius: 0;
  background: var(--bc-ink);
  margin-top: 0;
}

.bc-slider__input::-moz-range-thumb {
  width: 1px;
  height: 14px;
  border: 0;
  border-radius: 0;
  background: var(--bc-ink);
}

.bc-slider__input:focus-visible {
  outline: 2px solid var(--bc-accent);
  outline-offset: 2px;
}
</style>
