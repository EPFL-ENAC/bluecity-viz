<script setup lang="ts">
import BcDialogCard from '@/components/ui/BcDialogCard.vue'
import { useLayersStore } from '@/stores/layers'
import { splitSourceLabel } from '@/utils/sourceLabel'
import { computed } from 'vue'

defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [boolean] }>()

const layersStore = useLayersStore()

// One row per source that is not in the sidebar yet, with its SP code split out.
const rows = computed(() =>
  layersStore.availableSourcesForDialog.map((source) => {
    const { name, sp } = splitSourceLabel(source.label ?? source.id)
    return {
      id: source.id,
      name,
      sp,
      layers: layersStore.getLayersBySource(source.id).length
    }
  })
)

function addSource(id: string) {
  layersStore.addSources([id])
  emit('update:modelValue', false)
}
</script>

<template>
  <v-dialog
    :model-value="modelValue"
    max-width="720"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <BcDialogCard
      kicker="Datasets"
      title="Add data sources"
      flush
      @close="emit('update:modelValue', false)"
    >
      <div v-if="rows.length === 0" class="sources__empty bc-empty">
        All available data sources have been added.
      </div>

      <template v-else>
        <div class="sources__row sources__row--head">
          <span class="bc-micro">Project</span>
          <span class="bc-micro">Source</span>
          <span class="bc-micro">Layers</span>
          <span />
        </div>
        <div
          v-for="row in rows"
          :key="row.id"
          class="sources__row sources__row--item"
          @click="addSource(row.id)"
        >
          <span class="sources__sp">{{ row.sp }}</span>
          <span>{{ row.name }}</span>
          <span class="bc-meta">{{ row.layers }} {{ row.layers === 1 ? 'layer' : 'layers' }}</span>
          <button class="bc-link sources__add" @click.stop="addSource(row.id)">+ Add</button>
        </div>
      </template>

      <template #footer>
        <button class="bc-btn" @click="emit('update:modelValue', false)">Close</button>
      </template>
    </BcDialogCard>
  </v-dialog>
</template>

<style scoped>
.sources__row {
  display: grid;
  grid-template-columns: 90px 1fr 110px 80px;
  gap: 16px;
  align-items: center;
  padding: 9px 32px;
  border-bottom: 1px solid var(--bc-line);
  font-size: 14px;
}

.sources__row--head {
  padding: 6px 32px 8px;
}

.sources__row--item {
  cursor: pointer;
  transition: background var(--bc-t);
}

.sources__row--item:hover {
  background: var(--bc-hover);
}

.sources__sp {
  color: var(--bc-grey);
}

.sources__add {
  text-align: right;
}

.sources__empty {
  padding: 0 32px 8px;
}
</style>
