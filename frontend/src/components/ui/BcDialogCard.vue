<script setup lang="ts">
// The dialog frame of the design: mono kicker, 30/300 title, x on the right,
// hairline border, no radius, no shadow.
import BcIcon from './BcIcon.vue'

defineProps<{
  /** small uppercase mono label above the title */
  kicker: string
  title: string
  /** removes the body padding, for dialogs whose body is a full-width table */
  flush?: boolean
}>()

defineEmits<{ close: [] }>()
</script>

<template>
  <div class="bc-dialog">
    <div class="bc-dialog__head" :class="{ 'bc-dialog__head--flush': flush }">
      <div>
        <div class="bc-micro">{{ kicker }}</div>
        <div class="bc-dialog__title">{{ title }}</div>
      </div>
      <button class="bc-dialog__close" aria-label="Close" @click="$emit('close')">
        <BcIcon name="x" :size="18" />
      </button>
    </div>
    <div :class="flush ? '' : 'bc-dialog__body'">
      <slot />
    </div>
    <div v-if="$slots.footer" class="bc-dialog__footer">
      <slot name="footer" />
    </div>
  </div>
</template>

<style scoped>
.bc-dialog {
  background: var(--bc-panel);
  border: 1px solid var(--bc-line);
  color: var(--bc-ink);
}

.bc-dialog__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 26px 32px 18px;
}

.bc-dialog__title {
  font-size: 30px;
  font-weight: 300;
  letter-spacing: -0.02em;
  line-height: 1.15;
  margin-top: 4px;
}

.bc-dialog__close {
  background: none;
  border: 0;
  color: var(--bc-grey);
  cursor: pointer;
  padding: 4px;
  margin: -4px -4px 0 0;
  transition: color var(--bc-t);
}

.bc-dialog__close:hover {
  color: var(--bc-ink);
}

.bc-dialog__body {
  padding: 0 32px;
}

.bc-dialog__footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 16px 32px 22px;
}
</style>
