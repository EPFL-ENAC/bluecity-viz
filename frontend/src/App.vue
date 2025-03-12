<script setup lang="ts">
import { RouterView } from 'vue-router'
import ApiKeyDialog from './components/ApiKeyDialog.vue'
</script>

<template>
  <v-app>
    <v-main>
      <ApiKeyDialog />
      <RouterView />
    </v-main>
  </v-app>
</template>

<style lang="scss" scoped>
.v-app-bar {
  border-bottom: 1px solid rgb(var(--v-theme-primary));
}
</style>
