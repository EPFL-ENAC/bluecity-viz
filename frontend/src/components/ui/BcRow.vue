<script setup lang="ts">
// The list row of the Workbench design: hairline top, optional square check on
// the left, optional blue bar when active, mono meta on the right.
withDefaults(
  defineProps<{
    /** checkbox state, also drives the label colour (ink when on, grey when off) */
    on?: boolean
    /** draws the 3px accent bar on the left */
    active?: boolean
    /** show the square checkbox */
    check?: boolean
    disabled?: boolean
    /** indent, used for nested rows (investigations under a project) */
    indent?: boolean
  }>(),
  { on: false, active: false, check: true, disabled: false, indent: false }
)

defineEmits<{ click: [MouseEvent] }>()
</script>

<template>
  <div
    class="bc-row"
    :class="{ 'bc-row--disabled': disabled, 'bc-row--indent': indent }"
    :data-active="active ? 'true' : undefined"
    @click="!disabled && $emit('click', $event)"
  >
    <span v-if="check" class="bc-check" :data-on="on ? 'true' : 'false'" />
    <span class="bc-row__label" :class="{ 'bc-row__label--off': !on && check }">
      <slot />
    </span>
    <span v-if="$slots.meta" class="bc-row__meta"><slot name="meta" /></span>
    <span v-if="$slots.trailing" class="bc-row__trailing"><slot name="trailing" /></span>
  </div>
</template>

<style scoped>
.bc-row__label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: color var(--bc-t);
}

.bc-row__label--off {
  color: var(--bc-grey);
}

.bc-row__meta {
  font-family: var(--bc-font-mono);
  font-size: var(--bc-fs-micro);
  color: var(--bc-grey);
  flex: none;
}

.bc-row__trailing {
  display: flex;
  align-items: center;
  color: var(--bc-grey);
  opacity: 0;
  transition: opacity var(--bc-t);
  flex: none;
}

.bc-row:hover .bc-row__trailing {
  opacity: 1;
}

.bc-row__trailing:hover {
  color: var(--bc-ink);
}

.bc-row--indent {
  padding-left: 20px;
}

.bc-row--disabled {
  opacity: 0.45;
  cursor: default;
}

.bc-row--disabled:hover {
  background: transparent;
}
</style>
