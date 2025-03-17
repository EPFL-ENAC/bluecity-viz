<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useApiKeyStore } from '@/stores/apiKey'

const emit = defineEmits(['apiKeySaved'])

// Use the store
const apiKeyStore = useApiKeyStore()
const apiKey = ref('')
const errorMessage = ref('')
const isLoading = ref(false)
const dialogOpen = ref(true) // Start with dialog open

// Separate function to test API key validity
async function testApiKey(keyToTest: string): Promise<boolean> {
  isLoading.value = true
  errorMessage.value = ''

  try {
    // Test if the key works by making a small request
    const url = 'https://enacit4r-cdn.epfl.ch/bluecity/test.json' + '?apikey=' + keyToTest
    const response = await fetch(url, {
      // headers: {
      //   'X-Api-Key': keyToTest
      // }
    })

    if (!response.ok) {
      throw new Error('Invalid API key')
    }

    // Key is valid
    if (keyToTest !== apiKeyStore.apiKey) {
      // Only update if different from current key
      apiKeyStore.setApiKey(keyToTest)
    }

    emit('apiKeySaved', keyToTest)
    dialogOpen.value = false
    return true
  } catch (error) {
    // If testing the stored key and it fails, show error message
    if (keyToTest === apiKeyStore.apiKey) {
      errorMessage.value = 'Your saved API key is invalid. Please enter a valid key.'
      // Clear the invalid key from the store
      if (!import.meta.env.DEV) apiKeyStore.clearApiKey()
    } else {
      errorMessage.value = 'Invalid API key. Please try again.'
    }
    return false
  } finally {
    isLoading.value = false
  }
}

onMounted(async () => {
  // If there's a stored API key, test it automatically
  if (apiKeyStore.apiKey) {
    apiKey.value = apiKeyStore.apiKey
    await testApiKey(apiKeyStore.apiKey)
  }
})

const saveApiKey = async () => {
  if (!apiKey.value.trim()) {
    errorMessage.value = 'API key is required'
    return
  }

  // Use the separate test function
  await testApiKey(apiKey.value)
}

function forceValidate() {
  apiKeyStore.setApiKey(apiKey.value)
  dialogOpen.value = false
}
</script>

<template>
  <v-dialog v-model="dialogOpen" persistent max-width="500px">
    <v-card>
      <v-card-title class="text-h5">API Key Required</v-card-title>
      <v-card-text>
        <p v-if="errorMessage" class="mb-4">
          <v-alert type="warning" density="compact">{{ errorMessage }}</v-alert>
        </p>
        <p class="mb-4">Please enter your API key to access the BlueCity data.</p>
        <v-text-field
          v-model="apiKey"
          label="API Key"
          hide-details="auto"
          variant="outlined"
          @keyup.enter="saveApiKey"
        ></v-text-field>
      </v-card-text>
      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn color="secondary" @click="forceValidate"> Dev-only force validate </v-btn>
        <v-btn color="primary" :loading="isLoading" @click="saveApiKey"> Submit </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
