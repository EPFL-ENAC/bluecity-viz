// Vuetify re-themed to the Workbench design: square corners, no elevation,
// Suisse Int'l, hairline borders, Blue City blue as `primary`.
// Two themes: `workbench` (light) and `workbench-dark`. HomeView.vue switches
// between them from themeStore.isDark and mirrors the choice as
// data-theme="light|dark" on <html> for tokens.css.
import { createVuetify } from 'vuetify'
import { aliases, mdi } from 'vuetify/iconsets/mdi-svg'
import 'vuetify/styles'

export default createVuetify({
  icons: { defaultSet: 'mdi', aliases, sets: { mdi } },
  theme: {
    defaultTheme: 'workbench',
    themes: {
      workbench: {
        dark: false,
        colors: {
          background: '#FDFDFD',
          surface: '#FFFFFF',
          'surface-variant': '#F6F6F6',
          'on-surface-variant': '#141414',
          'on-surface': '#141414',
          'on-background': '#141414',
          primary: '#0500E1', // Blue City blue — active states, links
          'primary-darken-1': '#0400B8',
          secondary: '#141414', // ink — primary buttons are ink, not blue
          error: '#FF0000',
          warning: '#F5A623',
          success: '#699B32',
          info: '#0500E1'
        },
        variables: {
          'border-color': '#141414',
          'border-opacity': 0.08, // ~ #ECECEC hairline on white
          'medium-emphasis-opacity': 0.56, // ~ #8E8E8E
          'high-emphasis-opacity': 1
        }
      },
      'workbench-dark': {
        dark: true,
        colors: {
          background: '#141414',
          surface: '#1B1B1B',
          'surface-variant': '#222222',
          'on-surface-variant': '#F2F2F2',
          'on-surface': '#F2F2F2',
          'on-background': '#F2F2F2',
          primary: '#8583FF', // lifted Blue City blue
          'primary-darken-1': '#6E6BFF',
          secondary: '#F2F2F2', // ink is light; primary buttons become light-on-dark
          error: '#FF4D4D',
          warning: '#F5A623',
          success: '#7ED321',
          info: '#8583FF'
        },
        variables: {
          'border-color': '#F2F2F2',
          'border-opacity': 0.1, // ~ #2A2A2A hairline on #1B1B1B
          'medium-emphasis-opacity': 0.56,
          'high-emphasis-opacity': 1
        }
      }
    }
  },
  defaults: {
    global: { ripple: false },
    VBtn: { rounded: 0, elevation: 0, variant: 'outlined', color: 'secondary', class: 'bc-vbtn' },
    VCard: { rounded: 0, elevation: 0, variant: 'flat' },
    VDialog: { scrim: '#212121' },
    VSelect: { variant: 'outlined', density: 'compact', hideDetails: true, rounded: 0 },
    VTextField: { variant: 'outlined', density: 'compact', hideDetails: true, rounded: 0 },
    VChip: { rounded: 0, variant: 'outlined', size: 'small' },
    VProgressLinear: { color: 'secondary', height: 1 },
    VTooltip: { location: 'right' }
  }
})
