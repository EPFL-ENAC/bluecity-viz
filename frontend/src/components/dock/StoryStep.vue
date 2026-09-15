<script setup lang="ts">
import BcIcon from '@/components/ui/BcIcon.vue'

/**
 * One step of a tool's storyline: Model, Scenario or Results.
 *
 * Only one step is open at a time. The others fold to their head plus a one
 * line summary, so the user always sees what was set and where they are.
 *
 * - `open`: the step the user is on, its body is shown.
 * - `done`: a step the user can go back to. The whole head is a button, and
 *   the action label on the right says what the click does (Edit, Open).
 * - `todo`: a step not reachable yet. The summary says what unlocks it.
 */

const props = withDefaults(
  defineProps<{
    step: number
    title: string
    state: 'open' | 'done' | 'todo'
    /** the word on the right of a folded step, "Edit" or "Open" */
    action?: string
    /** a folded step that cannot be opened right now (a run is going) */
    busy?: boolean
  }>(),
  { action: 'Open', busy: false }
)

const emit = defineEmits<{ (event: 'open'): void }>()

function open(): void {
  if (props.state !== 'done' || props.busy) return
  emit('open')
}
</script>

<template>
  <section class="step" :data-state="state">
    <component
      :is="state === 'done' ? 'button' : 'div'"
      class="step__head"
      :type="state === 'done' ? 'button' : undefined"
      :disabled="state === 'done' && busy ? true : undefined"
      @click="open"
    >
      <span class="step__mark" aria-hidden="true">
        <BcIcon v-if="state === 'done'" name="check" />
        <template v-else>{{ step }}</template>
      </span>
      <span class="step__title">{{ title }}</span>
      <span v-if="state === 'done'" class="bc-micro step__action">{{ action }}</span>
    </component>

    <p v-if="state !== 'open' && $slots.summary" class="step__summary">
      <slot name="summary" />
    </p>

    <div v-if="state === 'open'" class="step__body">
      <slot />
    </div>
  </section>
</template>

<style scoped>
.step {
  border-bottom: 1px solid var(--bc-line);
}

.step__head {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 14px 22px 0;
  background: none;
  border: 0;
  font: inherit;
  color: var(--bc-ink);
  text-align: left;
}

.step[data-state='open'] .step__head {
  padding-bottom: 2px;
}

.step[data-state='done'] .step__head {
  cursor: pointer;
}

.step[data-state='done'] .step__head:disabled {
  cursor: default;
}

/* a 16px square with the step number, or a tick once the step is behind us */
.step__mark {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  flex: none;
  border: 1px solid var(--bc-ink);
  font-family: var(--bc-font-mono);
  font-size: var(--bc-fs-micro);
  line-height: 1;
}

.step[data-state='open'] .step__mark {
  background: var(--bc-ink);
  color: var(--bc-ground);
}

/* no box around the tick, or it reads as a checkbox you can toggle */
.step[data-state='done'] .step__mark {
  border-color: transparent;
}

.step[data-state='todo'] .step__mark {
  border-color: var(--bc-line);
  color: var(--bc-grey);
}

.step__title {
  flex: 1;
  font-size: var(--bc-fs-body);
  font-weight: 500;
}

.step[data-state='todo'] .step__title {
  color: var(--bc-grey);
  font-weight: 400;
}

.step__action {
  color: var(--bc-grey);
  transition: color var(--bc-t);
}

.step__head:not(:disabled):hover .step__action,
.step__head:focus-visible .step__action {
  color: var(--bc-ink);
  text-decoration: underline;
}

.step__head:disabled .step__action {
  opacity: 0.5;
}

.step__summary {
  margin: 2px 0 0;
  padding: 0 22px 14px 48px;
  font-size: var(--bc-fs-small);
  color: var(--bc-grey);
}

/* the body brings its own dock-section padding */
.step__body :deep(.dock-section:last-child) {
  border-bottom: 0;
}
</style>
