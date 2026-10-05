<script setup lang="ts">
// Segmented toggle: waste type, load unit, display mode.
withDefaults(
  defineProps<{
    modelValue: string
    options: { value: string; label: string }[]
    /** equal-width cells (waste type), otherwise the cells hug their label */
    equal?: boolean
    /** wrap the cells on a grid of this many columns, when one row is too narrow */
    columns?: number
  }>(),
  { equal: false, columns: undefined }
)

defineEmits<{ 'update:modelValue': [string] }>()
</script>

<template>
  <div
    class="bc-seg"
    :class="{ 'bc-seg--equal': equal, 'bc-seg--grid': columns }"
    :style="columns ? { '--bc-seg-columns': columns } : undefined"
  >
    <span
      v-for="(opt, i) in options"
      :key="opt.value"
      :class="{
        'bc-seg__cell--row-start': columns && i % columns === 0,
        'bc-seg__cell--below': columns && i >= columns
      }"
      :data-on="opt.value === modelValue ? 'true' : 'false'"
      @click="$emit('update:modelValue', opt.value)"
    >
      {{ opt.label }}
    </span>
  </div>
</template>

<style scoped>
.bc-seg--equal > * {
  flex: 1;
  text-align: center;
  padding: 8px 0;
  font-size: 10.5px;
  letter-spacing: 0.04em;
}

/* the same hairlines as one row: a line on the left of every cell but the
   first of its row, and one on top of every cell under the first row */
.bc-seg--grid {
  display: grid;
  grid-template-columns: repeat(var(--bc-seg-columns), 1fr);
}

.bc-seg--grid > .bc-seg__cell--row-start {
  border-left: 0;
}

.bc-seg--grid > .bc-seg__cell--below {
  border-top: 1px solid var(--bc-ink);
}
</style>
