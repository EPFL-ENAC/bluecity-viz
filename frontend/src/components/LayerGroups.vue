<script setup lang="ts">
import InfoTooltip from '@/components/InfoTooltip.vue'
import { mdiChevronDown, mdiChevronRight } from '@mdi/js'

// Define the types
type LayerItem = {
  id: string
  label: string
  info: string
  groupId: string
}

type LayerGroup = {
  id: string
  label: string
  expanded?: boolean
  layers: any[] // Allow any layer structure
}

// Define props
const { layerGroups, expandedGroups, layersSelected, possibleLayers } = defineProps({
  layerGroups: {
    type: Array as () => LayerGroup[],
    required: true
  },
  expandedGroups: {
    type: Object as () => Record<string, boolean>,
    required: true
  },
  layersSelected: {
    type: Array as () => string[],
    required: true
  },
  possibleLayers: {
    type: Array as () => LayerItem[],
    required: true
  }
})

// Define emits
const emit = defineEmits(['update:layers-selected', 'toggle-group'])

// Toggle group expansion
const toggleGroup = (groupId: string) => {
  emit('toggle-group', groupId)
}

// Handle layer selection changes
const updateSelectedLayers = (newValue: string[] | null) => {
  emit('update:layers-selected', newValue ?? [])
}
</script>

<template>
  <div>
    <div v-for="group in layerGroups" :key="group.id" class="layer-group mb-3">
      <!-- Group Header with Toggle -->
      <div class="d-flex align-center group-header" @click="toggleGroup(group.id)">
        <v-icon
          :icon="expandedGroups[group.id] ? mdiChevronDown : mdiChevronRight"
          size="small"
          class="mr-2"
        ></v-icon>
        <h4 class="text-uppercase mb-0">{{ group.label }}</h4>
      </div>

      <!-- Group Content (Collapsible) -->
      <div v-show="expandedGroups[group.id]" class="mt-2">
        <v-checkbox
          v-for="item in possibleLayers.filter((layer) => layer.groupId === group.id)"
          :key="item.id"
          :model-value="layersSelected"
          dense
          :value="item.id"
          @update:model-value="updateSelectedLayers"
        >
          <template #label>
            <h5 class="text-uppercase mb-0">{{ item.label }}</h5>
          </template>
          <template #append>
            <info-tooltip>{{ item.info }}</info-tooltip>
          </template>
        </v-checkbox>
      </div>
    </div>
  </div>
</template>

<style scoped>
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

.no-break {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 150px;
  display: inline-block;
}
</style>
