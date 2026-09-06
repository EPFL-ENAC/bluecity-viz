<script setup lang="ts">
import VisualizationsPanel from '@/components/panels/VisualizationsPanel.vue'
import InvestigationSection from '@/components/sidebar/InvestigationSection.vue'
import DatasetsSection from '@/components/sidebar/DatasetsSection.vue'
import LayersSection from '@/components/sidebar/LayersSection.vue'
import ToolsSection from '@/components/sidebar/ToolsSection.vue'
import BcIcon from '@/components/ui/BcIcon.vue'
import { ref, watch, provide } from 'vue'
import { useThemeStore } from '@/stores/theme'
import { useTheme } from 'vuetify'

// Map reference to pass to child components
const mapComponentRef = ref<any>(null)

// Provide map ref to children
provide('mapRef', mapComponentRef)

// Use theme store for the basemap selector
const themeStore = useThemeStore()

// Vuetify theme management
const vuetifyTheme = useTheme()

// The UI follows the basemap: dark basemap, dark UI. tokens.css reads
// data-theme on <html>, Vuetify reads its own theme name.
watch(
  () => themeStore.isDark,
  (isDark) => {
    document.documentElement.dataset.theme = isDark ? 'dark' : 'light'
    vuetifyTheme.change(isDark ? 'workbench-dark' : 'workbench')
  },
  { immediate: true }
)
</script>

<template>
  <div class="workbench">
    <aside class="sidebar">
      <div class="sidebar__head">
        <span class="sidebar__epfl">EPFL</span>
        <span class="sidebar__app">BlueCity Viz</span>
        <v-menu location="bottom end">
          <template #activator="{ props: menuProps }">
            <span v-bind="menuProps" class="bc-micro basemap">
              {{ themeStore.themeLabel }}
              <BcIcon name="chevron-down" />
            </span>
          </template>
          <div class="basemap__menu">
            <div
              v-for="item in themeStore.themes"
              :key="item.value"
              class="basemap__item"
              :data-on="item.value === themeStore.theme ? 'true' : 'false'"
              @click="themeStore.setTheme(item.value)"
            >
              {{ item.label }}
            </div>
          </div>
        </v-menu>
      </div>

      <div class="bc-scroll">
        <InvestigationSection />
        <DatasetsSection />
        <LayersSection />
        <ToolsSection />
      </div>
    </aside>

    <div class="stage">
      <VisualizationsPanel />
    </div>
  </div>
</template>

<style scoped>
.workbench {
  display: flex;
  height: 100vh;
  background: var(--bc-ground);
}

.sidebar {
  width: var(--bc-sidebar-w);
  flex: none;
  border-right: 1px solid var(--bc-line);
  background: var(--bc-panel);
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.sidebar__head {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px var(--bc-pad-x) 16px;
  border-bottom: 1px solid var(--bc-line);
}

.sidebar__epfl {
  font-weight: 700;
  font-size: 17px;
  letter-spacing: 0.04em;
}

.sidebar__app {
  font-size: 15px;
  font-weight: 400;
  letter-spacing: -0.01em;
}

.basemap {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
}

.basemap:hover {
  color: var(--bc-ink);
}

.basemap__menu {
  background: var(--bc-panel);
  border: 1px solid var(--bc-line);
  min-width: 140px;
}

.basemap__item {
  padding: 8px 14px;
  font-size: var(--bc-fs-body);
  cursor: pointer;
  transition: background var(--bc-t);
}

.basemap__item:hover {
  background: var(--bc-hover);
}

.basemap__item[data-on='true'] {
  color: var(--bc-accent);
}

.stage {
  flex: 1;
  position: relative;
  min-width: 0;
}
</style>
