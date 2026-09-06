<script setup lang="ts">
import { ref } from 'vue'
import { useLayersStore } from '@/stores/layers'
import AddSourceDialog from '@/components/dialogs/AddSourceDialog.vue'
import BcIcon from '@/components/ui/BcIcon.vue'
import BcRow from '@/components/ui/BcRow.vue'

const layersStore = useLayersStore()
const addSourceDialog = ref(false)
</script>

<template>
  <div class="bc-section">
    <div class="bc-section-head">
      <span class="bc-micro"
        >Datasets · {{ layersStore.availableResourceSourceObjects.length }}</span
      >
      <button class="bc-link" @click="addSourceDialog = true">+ Add</button>
    </div>

    <p v-if="layersStore.availableResourceSourceObjects.length === 0" class="bc-empty">
      No dataset yet. Use "+ Add" to pick one.
    </p>

    <BcRow
      v-for="source in layersStore.availableResourceSourceObjects"
      :key="source.id"
      :on="layersStore.isSourceEnabled(source.id)"
      @click="layersStore.toggleSource(source.id, !layersStore.isSourceEnabled(source.id))"
    >
      {{ source.label }}
      <template #meta> {{ layersStore.getLayersBySource(source.id).length }} layers </template>
      <template #trailing>
        <span title="Remove this source" @click.stop="layersStore.removeSource(source.id)">
          <BcIcon name="x" />
        </span>
      </template>
    </BcRow>

    <AddSourceDialog v-model="addSourceDialog" />
  </div>
</template>
