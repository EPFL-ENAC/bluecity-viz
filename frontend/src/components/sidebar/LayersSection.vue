<script setup lang="ts">
import BcRow from '@/components/ui/BcRow.vue'
import type { MapLayerConfig } from '@/config/layerTypes'
import { useLayersStore } from '@/stores/layers'
import { computed } from 'vue'

const layersStore = useLayersStore()

// Only the layers of the sources the user turned on, grouped by source label.
const layersBySource = computed(() => {
  const groups: { source: string; layers: MapLayerConfig[] }[] = []
  layersStore.availableResourceSourceObjects.forEach((source) => {
    if (!layersStore.isSourceEnabled(source.id)) return
    const layers = layersStore.getLayersBySource(source.id)
    if (layers.length > 0) groups.push({ source: source.label ?? source.id, layers })
  })
  return groups
})

const visibleCount = computed(() => layersStore.selectedLayers.length)

function toggleLayer(layerId: string) {
  const selected = [...layersStore.selectedLayers]
  const index = selected.indexOf(layerId)
  if (index >= 0) selected.splice(index, 1)
  else selected.push(layerId)
  layersStore.updateSelectedLayers(selected)
}
</script>

<template>
  <div class="bc-section">
    <div class="bc-micro layers__head">Layers · {{ visibleCount }} visible</div>

    <p v-if="layersBySource.length === 0" class="bc-empty">Turn a dataset on to see its layers.</p>

    <template v-for="group in layersBySource" :key="group.source">
      <div class="layers__caption">{{ group.source }}</div>
      <v-tooltip v-for="layer in group.layers" :key="layer.id" location="right" :text="layer.info">
        <template #activator="{ props: tooltipProps }">
          <div v-bind="layer.info ? tooltipProps : {}">
            <BcRow
              :on="layersStore.selectedLayers.includes(layer.layer.id)"
              @click="toggleLayer(layer.layer.id)"
            >
              {{ layer.label }}
            </BcRow>
          </div>
        </template>
      </v-tooltip>
    </template>
  </div>
</template>

<style scoped>
.layers__head {
  margin-bottom: 6px;
}

.layers__caption {
  font-size: var(--bc-fs-small);
  color: var(--bc-grey);
  padding: 8px 0 2px;
}
</style>
