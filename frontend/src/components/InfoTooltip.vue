<script setup lang="ts">
import { mdiInformationOutline } from '@mdi/js'
</script>

<template>
  <v-tooltip bottom max-width="512">
    <template #activator="{ props }">
      <v-icon size="small" class="opacity-60" v-bind="props" :icon="mdiInformationOutline" />
    </template>
    <slot />
  </v-tooltip>
</template>
