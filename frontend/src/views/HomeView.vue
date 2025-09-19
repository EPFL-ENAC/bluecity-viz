<script setup lang="ts">
import CollectionsPanel from '@/components/panels/CollectionsPanel.vue'
import VisualizationsPanel from '@/components/panels/VisualizationsPanel.vue'
import ResourcesPanel from '@/components/panels/ResourcesPanel.vue'
import { ref } from 'vue'
import { mdiMenu, mdiMenuOpen, mdiClose } from '@mdi/js'

// Navigation drawer states
const collectionsDrawer = ref(true)
const resourcesDrawer = ref(true)
</script>

<template>
  <v-layout class="fill-height">
    <!-- Top App Bar -->
    <v-app-bar class="border-b-sm" color="white" density="compact" flat>
      <!-- Collections Section (300px width to match drawer) -->
      <div class="collections-header border-e-sm">
        <v-btn
          :icon="collectionsDrawer ? mdiMenuOpen : mdiMenu"
          variant="text"
          @click="collectionsDrawer = !collectionsDrawer"
        />
        <span class="text-subtitle-1">COLLECTIONS</span>
      </div>
      <!-- Main Content Area (flexible) -->
      <div class="main-header">
        <div class="app-title">
          <span class="text-subtitle-1">BLUECITY VIZ</span>
        </div>
      </div>

      <!-- Resources Section (300px width to match drawer) -->
      <div class="resources-header border-s-sm">
        <span class="text-subtitle-1">RESOURCES</span>
        <v-btn
          :icon="resourcesDrawer ? mdiMenuOpen : mdiMenu"
          variant="text"
          @click="resourcesDrawer = !resourcesDrawer"
        />
      </div>
    </v-app-bar>

    <!-- Collections Navigation Drawer (Left) -->
    <v-navigation-drawer v-model="collectionsDrawer" location="start" width="300" permanent>
      <div class="pa-2">
        <CollectionsPanel />
      </div>
    </v-navigation-drawer>

    <!-- Resources Navigation Drawer (Right) -->
    <v-navigation-drawer v-model="resourcesDrawer" location="end" width="300" permanent>
      <div class="pa-2">
        <ResourcesPanel />
      </div>
    </v-navigation-drawer>

    <!-- Main Content Area -->
    <v-main>
      <VisualizationsPanel />
    </v-main>
  </v-layout>
</template>

<style scoped>
.collections-header,
.resources-header {
  width: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.main-header {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
