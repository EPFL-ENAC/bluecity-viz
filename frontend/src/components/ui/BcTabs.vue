<script setup lang="ts">
/**
 * The tab bar of the scenario workbench.
 *
 * Each tab carries a mono line under its name saying where that tool stands:
 * not run, a one line summary, or stale when the scenario moved since.
 */
export interface BcTab {
  id: string
  label: string
  meta: string
  stale?: boolean
}

defineProps<{ modelValue: string; tabs: BcTab[] }>()
const emit = defineEmits<{ (event: 'update:modelValue', value: string): void }>()
</script>

<template>
  <div class="tabs">
    <button
      v-for="tab in tabs"
      :key="tab.id"
      class="tab"
      type="button"
      :data-on="modelValue === tab.id"
      @click="emit('update:modelValue', tab.id)"
    >
      <span class="tab__label">{{ tab.label }}</span>
      <span class="tab__meta bc-micro" :data-stale="!!tab.stale">{{ tab.meta }}</span>
    </button>
  </div>
</template>

<style scoped>
.tabs {
  display: flex;
  border-bottom: 1px solid var(--bc-line);
  padding: 0 22px;
}

.tab {
  flex: 1;
  text-align: left;
  padding: 10px 0 9px;
  background: none;
  border: 0;
  /* the active underline sits on the section hairline, not under it */
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  color: var(--bc-grey);
  cursor: pointer;
}

.tab[data-on='true'] {
  border-bottom-color: var(--bc-ink);
  color: var(--bc-ink);
}

.tab__label {
  display: block;
  font-family: var(--bc-font-sans);
  font-size: var(--bc-fs-body);
}

.tab__meta {
  display: block;
  margin-top: 2px;
}

.tab__meta[data-stale='true'] {
  color: #b51f1f;
}
</style>
