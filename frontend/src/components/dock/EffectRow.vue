<script setup lang="ts">
import BcIcon from '@/components/ui/BcIcon.vue'

/**
 * One effect of a run: a wheel while it computes, a tick once it is done.
 *
 * The wheel only says the work has started, it is not a progress bar.
 */

export type EffectState = 'idle' | 'running' | 'done'

defineProps<{
  label: string
  state: EffectState
}>()
</script>

<template>
  <div class="effect" :data-state="state">
    <span class="effect__mark" aria-hidden="true">
      <BcIcon v-if="state === 'done'" name="check" :size="12" />
      <span v-else class="effect__ring" />
    </span>
    <span class="bc-micro effect__label">{{ label }}</span>
    <span class="effect__sr">
      {{ state === 'running' ? 'running' : state === 'done' ? 'done' : 'not run' }}
    </span>
  </div>
</template>

<style scoped>
.effect {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 0;
  border-top: 1px solid var(--bc-line);
}

.effect__mark {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 12px;
  height: 12px;
  flex: none;
  color: var(--bc-ink);
}

.effect__ring {
  display: block;
  width: 11px;
  height: 11px;
  border: 1px solid var(--bc-line);
  border-radius: 50%;
}

.effect[data-state='running'] .effect__ring {
  border-top-color: var(--bc-ink);
  animation: effect-spin 0.8s linear infinite;
}

.effect__label {
  color: var(--bc-grey);
}

.effect[data-state='running'] .effect__label,
.effect[data-state='done'] .effect__label {
  color: var(--bc-ink);
}

/* read by screen readers, not shown */
.effect__sr {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}

@keyframes effect-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .effect[data-state='running'] .effect__ring {
    animation-duration: 2.4s;
  }
}
</style>
