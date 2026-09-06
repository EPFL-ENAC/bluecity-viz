<script setup lang="ts">
// Feather icons (https://feathericons.com), 2px stroke, currentColor.
// Inlined so we do not pull a whole icon package for 9 glyphs.
withDefaults(
  defineProps<{
    name:
      | 'chevron-down'
      | 'chevron-right'
      | 'plus'
      | 'x'
      | 'share-2'
      | 'edit-2'
      | 'trash-2'
      | 'info'
      | 'map-pin'
    size?: number
  }>(),
  { size: 12 }
)
</script>

<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
    class="bc-icon"
    aria-hidden="true"
  >
    <polyline v-if="name === 'chevron-down'" points="6 9 12 15 18 9" />
    <polyline v-else-if="name === 'chevron-right'" points="9 18 15 12 9 6" />
    <template v-else-if="name === 'plus'">
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </template>
    <template v-else-if="name === 'x'">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </template>
    <template v-else-if="name === 'share-2'">
      <circle cx="18" cy="5" r="3" />
      <circle cx="6" cy="12" r="3" />
      <circle cx="18" cy="19" r="3" />
      <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
      <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
    </template>
    <path
      v-else-if="name === 'edit-2'"
      d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"
    />
    <template v-else-if="name === 'trash-2'">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    </template>
    <template v-else-if="name === 'info'">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="16" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12.01" y2="8" />
    </template>
    <template v-else-if="name === 'map-pin'">
      <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
      <circle cx="12" cy="10" r="3" />
    </template>
  </svg>
</template>

<style scoped>
.bc-icon {
  flex: none;
  display: block;
}
</style>
