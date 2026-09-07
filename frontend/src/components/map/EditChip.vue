<script setup lang="ts">
// Shown while the graph is being edited, top left of the map.
</script>

<template>
  <div class="edit-chip bc-micro">
    <span class="edit-chip__dot"></span>
    <span class="edit-chip__on">Edit mode</span>
    <span>Click an edge · Esc to leave</span>
  </div>
</template>

<style scoped>
.edit-chip {
  position: absolute;
  left: 16px;
  top: 16px;
  z-index: 3;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 8px 12px;
  background: var(--bc-legend-bg);
}

.edit-chip__dot {
  width: 5px;
  height: 5px;
  background: var(--bc-accent);
  flex: none;
}

.edit-chip__on {
  color: var(--bc-ink);
}
</style>
