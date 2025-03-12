import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export const useApiKeyStore = defineStore('apiKey', () => {
  const API_KEY_STORAGE_KEY = 'bluecity-api-key'
  const apiKey = ref<string | null>(localStorage.getItem(API_KEY_STORAGE_KEY))

  const hasApiKey = computed(() => !!apiKey.value)

  function setApiKey(key: string) {
    apiKey.value = key
    localStorage.setItem(API_KEY_STORAGE_KEY, key)
  }

  function clearApiKey() {
    apiKey.value = null
    localStorage.removeItem(API_KEY_STORAGE_KEY)
  }

  return {
    apiKey,
    hasApiKey,
    setApiKey,
    clearApiKey
  }
})
