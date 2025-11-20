<script setup lang="ts">
import CollectionsPanel from '@/components/panels/CollectionsPanel.vue'
import VisualizationsPanel from '@/components/panels/VisualizationsPanel.vue'
import ResourcesPanel from '@/components/panels/ResourcesPanel.vue'
import TrafficAnalysisPanelDeckGL from '@/components/panels/TrafficAnalysisPanelDeckGL.vue'
import { ref, watch, provide } from 'vue'
import { mdiMenu, mdiMenuOpen } from '@mdi/js'
import { useThemeStore } from '@/stores/theme'
import { useTheme } from 'vuetify'

// Navigation drawer states
const collectionsDrawer = ref(true)
const resourcesDrawer = ref(true)

// Map reference to pass to child components
const mapComponentRef = ref<any>(null)

// Provide map ref to children
provide('mapRef', mapComponentRef)

// Use theme store for theme selector
const themeStore = useThemeStore()

// Vuetify theme management
const vuetifyTheme = useTheme()

// Watch for theme changes and update Vuetify theme
watch(
  () => themeStore.theme,
  (newTheme) => {
    const vuetifyThemeName = newTheme === 'style/light.json' ? 'light' : 'dark'
    console.log('Updating Vuetify theme to:', vuetifyThemeName)
    vuetifyTheme.change(vuetifyThemeName)
  },
  { immediate: true }
)
</script>

<template>
  <v-layout class="fill-height">
    <!-- Top App Bar -->
    <v-app-bar class="border-b-sm" flat>
      <!-- Collections Section (300px width to match drawer) -->
      <div class="collections-header">
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
      <div class="theme-selector ml-4">
        <v-select
          v-model="themeStore.theme"
          :items="themeStore.themes"
          item-value="value"
          item-title="label"
          label="Theme"
          density="compact"
          variant="plain"
          hide-details
          style="width: 150px"
        />
      </div>
      <!-- Resources Section (300px width to match drawer) -->
      <div class="resources-header">
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
      <!-- Add Traffic Analysis Panel (Deck.gl version) -->
      <TrafficAnalysisPanelDeckGL />
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
