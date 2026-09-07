import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'

const THEME_STORAGE_KEY = 'bluecity-viz-theme'
const DEFAULT_THEME = 'substrat'

// Available basemaps. "substrat" / "substrat-dark" are built by
// utils/epflBasemap.ts, the others are style JSON files from public/style/.
const THEMES = [
  { value: 'substrat', label: 'Substrat' },
  { value: 'substrat-dark', label: 'Substrat dark' },
  { value: 'style/light.json', label: 'Light' },
  { value: 'style/none.json', label: 'None' }
]

// "Trait" drew every road itself, which fights the street graph overlay. A
// stored Trait value reads back as its Substrat counterpart.
const LEGACY: Record<string, string> = {
  trait: 'substrat',
  'trait-dark': 'substrat-dark'
}

export const useThemeStore = defineStore('theme', () => {
  // Initialize theme from localStorage or use default
  const getStoredTheme = (): string => {
    try {
      const stored = localStorage.getItem(THEME_STORAGE_KEY)
      if (!stored) return DEFAULT_THEME
      const value = LEGACY[stored] ?? stored
      // an old value (style/dark.json) is no longer offered, fall back
      if (THEMES.some((t) => t.value === value)) return value
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

  // The UI follows the basemap: only "substrat-dark" is a dark ground.
  const isDark = computed(() => theme.value === 'substrat-dark')
  // "substrat" basemaps are drawn by the EPFL engine, the others are style URLs.
  const isSubstrat = computed(() => theme.value.startsWith('substrat'))
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
    isSubstrat,
    themeLabel,

    // Actions
    setTheme
  }
})
