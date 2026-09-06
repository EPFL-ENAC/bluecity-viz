<script lang="ts" setup>
// A 1px ink line at the top of the map area, instead of a spinner over the map.
defineProps<{ loading: boolean }>()
</script>

<template>
  <v-progress-linear
    v-if="loading"
    class="loading-bar"
    color="secondary"
    :height="1"
    indeterminate
  />
</template>

<style scoped>
.loading-bar {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  z-index: 10;
}
</style>
