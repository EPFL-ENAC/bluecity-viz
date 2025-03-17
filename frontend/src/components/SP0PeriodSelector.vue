<script setup lang="ts">
import { useLayersStore } from '@/stores/layers'

// For direct store integration
const layersStore = useLayersStore()

const periods = ['2011-2014', '2015-2019', '2020-2023']
</script>

<template>
  <div class="period-selector">
    <div class="period-options">
      <v-btn-toggle
        v-model="layersStore.sp0Period"
        color="grey"
        mandatory
        class="period-toggle ga-1"
      >
        <v-btn
          v-for="period in periods"
          :key="period"
          :value="period"
          :text="period"
          density="compact"
          class="period-btn"
        ></v-btn>
      </v-btn-toggle>
    </div>
  </div>
</template>

<style scoped>
.period-selector {
  margin-bottom: 16px;
  padding: 0 1rem;
  width: 100%;
}

.period-options {
  display: flex;
  justify-content: center;
}

.period-toggle {
  width: 100%;
  outline: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  display: flex;
  flex-direction: column;
  height: 8rem;
}

.period-btn {
  flex-grow: 1;
}
</style>
