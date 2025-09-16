<script setup lang="ts">
import CollectionsPanel from '@/components/CollectionsPanel.vue'
import VisualizationsPanel from '@/components/VisualizationsPanel.vue'
import ResourcesPanel from '@/components/ResourcesPanel.vue'
</script>

<template>
  <v-container class="fill-height pa-0" fluid>
    <v-row class="fill-height pa-0 ma-0">
      <!-- Collections Column (Left) -->
      <v-col cols="2" class="fill-height overflow-y-auto collections-col border-e-md">
        <CollectionsPanel />
      </v-col>

      <!-- Visualizations Column (Center) -->
      <v-col cols="7" class="fill-height visualizations-col pa-0">
        <VisualizationsPanel />
      </v-col>

      <!-- Resources Column (Right) -->
      <v-col cols="3" class="fill-height overflow-y-auto resources-col border-s-md">
        <ResourcesPanel />
      </v-col>
    </v-row>
  </v-container>
</template>

<style scoped>
.collections-col,
.resources-col {
  max-height: 100vh;
}
</style>
