import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'

const THEME_STORAGE_KEY = 'bluecity-viz-theme'
const DEFAULT_THEME = 'trait'

// Available basemaps. "trait" / "trait-dark" are built by utils/epflBasemap.ts,
// the others are style JSON files served from public/style/.
const THEMES = [
  { value: 'trait', label: 'Trait' },
  { value: 'trait-dark', label: 'Trait dark' },
  { value: 'style/light.json', label: 'Light' },
  { value: 'style/none.json', label: 'None' }
]

export const useThemeStore = defineStore('theme', () => {
  // Initialize theme from localStorage or use default
  const getStoredTheme = (): string => {
    try {
      const stored = localStorage.getItem(THEME_STORAGE_KEY)
      // an old value (style/dark.json) is no longer offered, fall back
      if (stored && THEMES.some((t) => t.value === stored)) return stored
      return DEFAULT_THEME
    } catch (error) {
      console.warn('Failed to load theme from localStorage:', error)
      return DEFAULT_THEME
    }
  }

  // Theme state
  const theme = ref(getStoredTheme())

  // Available themes
  const themes = THEMES

  // The UI follows the basemap: only "trait-dark" is a dark ground.
  const isDark = computed(() => theme.value === 'trait-dark')
  // "trait" basemaps are drawn by the EPFL engine, the others are style URLs.
  const isTrait = computed(() => theme.value.startsWith('trait'))
  const themeLabel = computed(
    () => themes.find((t) => t.value === theme.value)?.label ?? theme.value
  )

  // Actions
  const setTheme = (newTheme: string) => {
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

    // Getters
    isDark,
    isTrait,
    themeLabel,

    // Actions
    setTheme
  }
})
