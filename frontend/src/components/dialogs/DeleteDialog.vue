<script setup lang="ts">
import BcDialogCard from '@/components/ui/BcDialogCard.vue'
import { computed } from 'vue'

const props = defineProps<{
  modelValue: boolean
  type: 'project' | 'investigation'
  name: string
  investigationCount?: number
}>()

const emit = defineEmits<{
  'update:modelValue': [boolean]
  confirm: []
  cancel: []
}>()

const kicker = computed(() =>
  props.type === 'project' ? 'Delete project' : 'Delete investigation'
)

const body = computed(() => {
  if (props.type === 'project' && props.investigationCount) {
    return `This also deletes its ${props.investigationCount} investigations. This action cannot be undone.`
  }
  return 'This action cannot be undone.'
})
</script>

<template>
  <v-dialog
    :model-value="modelValue"
    max-width="480"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <BcDialogCard :kicker="kicker" :title="name" @close="emit('cancel')">
      <p class="delete__text">{{ body }}</p>
      <template #footer>
        <button class="bc-btn" @click="emit('cancel')">Cancel</button>
        <button class="bc-btn bc-btn--danger" @click="emit('confirm')">Delete</button>
      </template>
    </BcDialogCard>
  </v-dialog>
</template>

<style scoped>
.delete__text {
  margin: 0;
  font-size: 14px;
  line-height: 1.5;
}
</style>
