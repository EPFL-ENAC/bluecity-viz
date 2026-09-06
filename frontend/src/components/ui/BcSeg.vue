<script setup lang="ts">
// Segmented toggle: waste type, load unit, display mode.
withDefaults(
  defineProps<{
    modelValue: string
    options: { value: string; label: string }[]
    /** equal-width cells (waste type), otherwise the cells hug their label */
    equal?: boolean
  }>(),
  { equal: false }
)

defineEmits<{ 'update:modelValue': [string] }>()
</script>

<template>
  <div class="bc-seg" :class="{ 'bc-seg--equal': equal }">
    <span
      v-for="opt in options"
      :key="opt.value"
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
</style>
