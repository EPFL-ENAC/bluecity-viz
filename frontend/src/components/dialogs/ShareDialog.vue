<script setup lang="ts">
import { ref } from 'vue'
import BcDialogCard from '@/components/ui/BcDialogCard.vue'

defineProps<{ modelValue: boolean; url: string; name: string }>()
const emit = defineEmits<{ 'update:modelValue': [boolean] }>()

const copied = ref(false)

async function copyToClipboard(url: string) {
  try {
    await navigator.clipboard.writeText(url)
  } catch (error) {
    console.warn('Failed to copy to clipboard:', error)
    // Fallback for older browsers
    const textArea = document.createElement('textarea')
    textArea.value = url
    document.body.appendChild(textArea)
    textArea.select()
    document.execCommand('copy')
    document.body.removeChild(textArea)
  }
  copied.value = true
  setTimeout(() => {
    copied.value = false
  }, 2000)
}

function close() {
  copied.value = false
  emit('update:modelValue', false)
}
</script>

<template>
  <v-dialog
    :model-value="modelValue"
    max-width="560"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <BcDialogCard kicker="Share" :title="name" @close="close">
      <p class="share__text">
        Anyone with this link sees the same setup — selected sources, layers and edge modifications.
      </p>
      <div class="share__field">
        <span class="share__url">{{ url }}</span>
        <button class="bc-btn bc-btn--primary share__copy" @click="copyToClipboard(url)">
          Copy
        </button>
      </div>
      <div v-if="copied" class="bc-micro share__copied">Copied to clipboard</div>
    </BcDialogCard>
  </v-dialog>
</template>

<style scoped>
.share__text {
  margin: 0 0 18px;
  font-size: 14px;
  line-height: 1.5;
}

.share__field {
  display: flex;
  border: 1px solid var(--bc-ink);
}

.share__url {
  flex: 1;
  min-width: 0;
  padding: 10px 12px;
  font-family: var(--bc-font-mono);
  font-size: 11px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.share__copy {
  border: 0;
  padding: 0 16px;
}

.share__copied {
  margin-top: 10px;
  padding-bottom: 24px;
  color: var(--bc-accent);
}
</style>
