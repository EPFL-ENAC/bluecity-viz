/// <reference types="vite/client" />

// vuetify/styles points at a .css file through the export map, and that file
// has no types. TypeScript 6 refuses a side-effect import without one
// (TS2882), so we declare it here.
declare module 'vuetify/styles'
