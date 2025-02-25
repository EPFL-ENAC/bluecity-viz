<script setup lang="ts">
import JsonWebMap from '@/components/JsonWebMap.vue'

const styleUrl = 'style/dark.json'
</script>

<template>
  <JsonWebMap class="border-t-md border-b-md" :style-url="styleUrl" />
</template>
