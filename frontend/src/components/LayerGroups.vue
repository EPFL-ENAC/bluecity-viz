<script setup lang="ts">
import InfoTooltip from '@/components/InfoTooltip.vue'
import { mdiChevronDown, mdiChevronRight, mdiEyeOutline, mdiEyeOffOutline } from '@mdi/js'
import { useLayersStore } from '@/stores/layers'
import SP0PeriodSelector from './SP0PeriodSelector.vue'

// Use the store - now the component gets everything from the store, no props needed
const layersStore = useLayersStore()
</script>

<template>
  <div>
    <div v-for="group in layersStore.layerGroups" :key="group.id" class="layer-group mb-3">
      <!-- Group Header with Toggle -->
      <div class="d-flex align-center justify-space-between">
        <!-- Group Title -->
        <h4
          class="text-uppercase mb-0 flex-grow-1 group-header"
          @click="layersStore.toggleGroup(group.id)"
        >
          <v-icon
            :icon="layersStore.expandedGroups[group.id] ? mdiChevronDown : mdiChevronRight"
            size="small"
            class="mr-2 d"
          ></v-icon>
          {{ group.label }}
        </h4>

        <!-- Visibility Toggle Icon -->
        <v-icon
          :icon="layersStore.isGroupVisible(group.id) ? mdiEyeOutline : mdiEyeOffOutline"
          size="small"
          class="visibility-toggle"
          :class="{ active: layersStore.isGroupVisible(group.id) }"
          :title="layersStore.isGroupVisible(group.id) ? 'Hide layer group' : 'Show layer group'"
          @click.stop="layersStore.toggleGroupVisibility(group.id)"
        ></v-icon>
      </div>

      <!-- Group Content (Collapsible) -->
      <div v-show="layersStore.expandedGroups[group.id]" class="mt-2">
        <div v-if="group.id == 'sp0_migration'">
          <SP0PeriodSelector></SP0PeriodSelector>
        </div>
        <!-- Use checkbox for multiple selection groups -->
        <template v-if="group.multiple">
          <v-checkbox
            v-for="item in layersStore.possibleLayers.filter((layer) => layer.groupId === group.id)"
            :key="item.id"
            :model-value="layersStore.selectedLayers"
            dense
            :value="item.id"
            @update:model-value="layersStore.updateSelectedLayers"
          >
            <template #label>
              <h5 class="text-uppercase mb-0">{{ item.label }}</h5>
            </template>
            <template #append>
              <info-tooltip>{{ item.info }}</info-tooltip>
            </template>
          </v-checkbox>
        </template>

        <!-- Use radio buttons for single selection groups -->
        <template v-else>
          <v-radio-group
            :model-value="
              layersStore.selectedLayers.find((id) => {
                const layer = layersStore.possibleLayers.find((l) => l.id === id)
                return layer && layer.groupId === group.id
              }) || ''
            "
          >
            <div
              v-for="item in layersStore.possibleLayers.filter(
                (layer) => layer.groupId === group.id
              )"
              :key="item.id"
              class="d-flex flex-grow-1 flex-row align-center"
            >
              <v-radio
                :value="item.id"
                dense
                @change="layersStore.updateSingleLayerSelection(group.id, item.id)"
              >
                <template #label>
                  <h5 class="text-uppercase flex-grow-1 mb-0">{{ item.label }}</h5>
                </template>
              </v-radio>
              <info-tooltip class="ml-2">{{ item.info }}</info-tooltip>
            </div>
          </v-radio-group>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Styles remain the same */
.layer-group {
  border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  padding-bottom: 8px;
}

.group-header {
  cursor: pointer;
  padding: 8px 0;
}

.group-header:hover {
  background-color: rgba(var(--v-theme-on-surface), 0.05);
}

.visibility-toggle {
  opacity: 0.6;
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.visibility-toggle:hover {
  opacity: 1;
  transform: scale(1.1);
}

.visibility-toggle.active {
  opacity: 1;
  color: var(--v-theme-primary);
}

.no-break {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 150px;
  display: inline-block;
}
</style>
