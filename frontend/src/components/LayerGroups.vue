<script setup lang="ts">
import InfoTooltip from '@/components/InfoTooltip.vue'
import { mdiChevronDown, mdiChevronRight, mdiEyeOutline, mdiEyeOffOutline } from '@mdi/js'

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
  multiple: boolean // Whether multiple selection is allowed
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

// Handle layer selection changes for checkboxes (multiple selection)
const updateSelectedLayers = (newValue: string[] | null) => {
  emit('update:layers-selected', newValue ?? [])
}

// Handle layer selection changes for radio buttons (single selection)
const updateSingleLayerSelection = (groupId: string, layerId: string) => {
  // Create a new array without any layers from this group
  const otherGroupLayers = layersSelected.filter((id) => {
    const layer = possibleLayers.find((l) => l.id === id)
    return layer && layer.groupId !== groupId
  })

  // Add the selected layer and emit the updated array
  emit('update:layers-selected', [...otherGroupLayers, layerId])
}

// Helper to check if a radio button should be selected
const isLayerSelected = (layerId: string): boolean => {
  return layersSelected.includes(layerId)
}

// Check if any layer in the group is selected
const isGroupVisible = (groupId: string): boolean => {
  return layersSelected.some((id) => {
    const layer = possibleLayers.find((l) => l.id === id)
    return layer && layer.groupId === groupId
  })
}

// Toggle all layers in a group
const toggleGroupVisibility = (event: Event, groupId: string) => {
  event.stopPropagation() // Prevent triggering the group expansion

  const groupLayers = possibleLayers.filter((layer) => layer.groupId === groupId)
  const groupLayerIds = groupLayers.map((layer) => layer.id)

  // Check if any layer from this group is currently selected
  const isVisible = isGroupVisible(groupId)

  if (isVisible) {
    // If visible, remove all layers from this group
    const filteredLayers = layersSelected.filter((id) => !groupLayerIds.includes(id))
    emit('update:layers-selected', filteredLayers)
  } else {
    // If not visible, add layers according to group's selection mode
    const group = layerGroups.find((g) => g.id === groupId)
    if (group?.multiple) {
      // For multiple selection groups, add all layers
      const newSelection = [...layersSelected, ...groupLayerIds]
      emit('update:layers-selected', newSelection)
    } else if (groupLayers.length > 0) {
      // For single selection groups, add only the first layer
      const otherGroupLayers = layersSelected.filter((id) => {
        const layer = possibleLayers.find((l) => l.id === id)
        return layer && layer.groupId !== groupId
      })
      emit('update:layers-selected', [...otherGroupLayers, groupLayerIds[0]])
    }
  }
}
</script>

<template>
  <div>
    <div v-for="group in layerGroups" :key="group.id" class="layer-group mb-3">
      <!-- Group Header with Toggle -->
      <div class="d-flex align-center justify-space-between">
        <!-- Group Title -->
        <h4 class="text-uppercase mb-0 flex-grow-1 group-header" @click="toggleGroup(group.id)">
          <v-icon
            :icon="expandedGroups[group.id] ? mdiChevronDown : mdiChevronRight"
            size="small"
            class="mr-2 d"
          ></v-icon
          >{{ group.label }}
        </h4>

        <!-- Visibility Toggle Icon -->
        <v-icon
          :icon="isGroupVisible(group.id) ? mdiEyeOutline : mdiEyeOffOutline"
          size="small"
          class="visibility-toggle"
          :class="{ active: isGroupVisible(group.id) }"
          @click="(e) => toggleGroupVisibility(e, group.id)"
          :title="isGroupVisible(group.id) ? 'Hide layer group' : 'Show layer group'"
        ></v-icon>
      </div>

      <!-- Group Content (Collapsible) -->
      <div v-show="expandedGroups[group.id]" class="mt-2">
        <!-- Use checkbox for multiple selection groups -->
        <template v-if="group.multiple">
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
        </template>

        <!-- Use radio buttons for single selection groups -->
        <template v-else>
          <v-radio-group
            :model-value="
              layersSelected.find((id) => {
                const layer = possibleLayers.find((l) => l.id === id)
                return layer && layer.groupId === group.id
              }) || ''
            "
          >
            <div
              v-for="item in possibleLayers.filter((layer) => layer.groupId === group.id)"
              :key="item.id"
              class="d-flex flex-grow-1 flex-row align-center"
            >
              <v-radio
                :value="item.id"
                dense
                @change="updateSingleLayerSelection(group.id, item.id)"
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
