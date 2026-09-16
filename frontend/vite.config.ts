import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import vuetify from 'vite-plugin-vuetify'
// defineConfig comes from vitest/config, not vite, so the test block below is typed.
import { configDefaults, defineConfig } from 'vitest/config'

// https://vitejs.dev/config/
// Git worktrees run one backend and one vite per branch. wtx writes the ports
// in .env.worktree and every pane exports them, so this config reads them from
// the environment. The main checkout keeps 5173 and 8000.
const backendPort = process.env.BACKEND_PORT || '8000'

// One vendor chunk per big library, so a change in app code does not
// invalidate the cached maplibre / vuetify bundles.
const vendorChunks = [
  { name: 'maplibre', test: /[\\/]node_modules[\\/](maplibre-gl|pmtiles)[\\/]/ },
  { name: 'vuetify', test: /[\\/]node_modules[\\/]vuetify[\\/]/ },
  { name: 'd3', test: /[\\/]node_modules[\\/](d3-[a-z-]+|internmap)[\\/]/ }
]

export default defineConfig({
  base: process.env.BASE_URL || '/',
  server: {
    port: Number(process.env.FRONTEND_PORT) || 5173,
    proxy: {
      // The frontend always calls the backend on a relative /api path, in dev
      // and in prod, so a worktree hits its own backend and never a neighbour's.
      '^/api/.*': {
        target: `http://127.0.0.1:${backendPort}`,
        changeOrigin: true
      },
      '^/data.*': {
        target: `http://127.0.0.1:${backendPort}/data`,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/data/, '')
      }
    }
  },
  plugins: [vue(), vuetify()],
  optimizeDeps: {
    // maplibre 6 loads its worker from a second entry, maplibre-gl-worker.mjs.
    // The dep optimizer bundles the main entry and never emits that file, so
    // in dev the worker request hangs and no tile is ever decoded. The map
    // stays blank with no error. Excluding it serves maplibre as plain ESM.
    exclude: ['maplibre-gl']
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  build: {
    // .map files are emitted but not referenced from the bundles
    sourcemap: 'hidden',
    // vite 8 bundles with rolldown: manualChunks is gone, groups replace it
    rolldownOptions: {
      output: {
        codeSplitting: { groups: vendorChunks }
      }
    }
  },
  test: {
    // The unit tests only need localStorage and window.location, but jsdom
    // costs little and keeps the door open for component tests.
    environment: 'jsdom',
    exclude: [...configDefaults.exclude, 'e2e/*']
  }
})
