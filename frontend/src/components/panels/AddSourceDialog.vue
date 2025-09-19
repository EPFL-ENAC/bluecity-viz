<script setup lang="ts">
import { useLayersStore } from '@/stores/layers'
import { mdiPlus } from '@mdi/js'

// Props
interface Props {
  modelValue: boolean
}

defineProps<Props>()

// Emits
interface Emits {
  (e: 'update:modelValue', value: boolean): void
}

const emit = defineEmits<Emits>()

// Use the layers store
const layersStore = useLayersStore()

// Handle dialog close
function closeDialog() {
  emit('update:modelValue', false)
}

// Handle source addition and close dialog
function handleAddSource(sourceId: string) {
  layersStore.addSources([sourceId])
  closeDialog()
}
</script>

<template>
  <v-dialog :model-value="modelValue" max-width="600" @update:model-value="closeDialog">
    <v-card class="pa-6">
      <v-card-title>
        <span class="text-h5">Add Data Sources</span>
      </v-card-title>
      <v-card-text>
        <div v-if="layersStore.availableSourcesForDialog.length === 0" class="text-center py-4">
          <p>All available data sources have been added!</p>
        </div>
        <div v-else>
          <p class="mb-3">Select data sources to add to your workspace:</p>
          <v-list density="compact" class="py-0">
            <v-list-item
              v-for="source in layersStore.availableSourcesForDialog"
              :key="source.id"
              class="px-2 py-1"
              min-height="48"
            >
              <template #prepend>
                <v-btn
                  :icon="mdiPlus"
                  size="x-small"
                  variant="outlined"
                  color="primary"
                  class="mr-3"
                  @click="handleAddSource(source.id)"
                />
              </template>
              <v-list-item-title class="text-body-2">{{ source.label }}</v-list-item-title>
              <v-list-item-subtitle class="text-caption">
                {{ layersStore.getLayersBySource(source.id).length }} layers
              </v-list-item-subtitle>
            </v-list-item>
          </v-list>
        </div>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn text @click="closeDialog"> Close </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
