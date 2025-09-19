<script setup lang="ts">
// Collections Panel - Left column component
</script>

<template>
  <v-card flat class="d-flex flex-column">
    <v-card-title class="flex-shrink-0 text-center pa-2">
      <h6 class="w-100">COLLECTIONS</h6>
    </v-card-title>
    <v-card-text class="flex-grow-1 overflow-y-auto">
      <!-- Placeholder for configuration selection -->
      <div class="mb-6 flex-shrink-0">
        <h5 class="text-subtitle-1 mb-2">Configuration</h5>
        <v-select
          :items="['Default', 'Custom 1', 'Custom 2']"
          label="Select Configuration"
          variant="outlined"
          density="compact"
        ></v-select>
      </div>
    </v-card-text>
  </v-card>
</template>
