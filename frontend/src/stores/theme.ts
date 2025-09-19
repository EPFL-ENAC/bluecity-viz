import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

const THEME_STORAGE_KEY = 'bluecity-viz-theme'
const DEFAULT_THEME = 'style/light.json'

export const useThemeStore = defineStore('theme', () => {
  // Initialize theme from localStorage or use default
  const getStoredTheme = (): string => {
    try {
      const stored = localStorage.getItem(THEME_STORAGE_KEY)
      return stored || DEFAULT_THEME
    } catch (error) {
      console.warn('Failed to load theme from localStorage:', error)
      return DEFAULT_THEME
    }
  }

  // Theme state
  const theme = ref(getStoredTheme())

  // Available themes
  const themes = [
    { value: 'style/light.json', label: 'Light' },
    { value: 'style/dark.json', label: 'Dark' },
    { value: 'style/none.json', label: 'None' }
  ]

  // Actions
  const setTheme = (newTheme: string) => {
    console.log('Setting theme to:', newTheme)
    theme.value = newTheme
  }

  // Watch for theme changes and persist to localStorage
  watch(
    theme,
    (newTheme) => {
      try {
        localStorage.setItem(THEME_STORAGE_KEY, newTheme)
      } catch (error) {
        console.warn('Failed to save theme to localStorage:', error)
      }
    },
    { immediate: false }
  )

  return {
    // State
    theme,
    themes,

    // Actions
    setTheme
  }
})
