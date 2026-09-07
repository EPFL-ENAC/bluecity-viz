/// <reference types="vitest/config" />
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vuetify from 'vite-plugin-vuetify'
import { configDefaults } from 'vitest/config'

// https://vitejs.dev/config/
// Git worktrees run one backend and one vite per branch. wt-setup.sh writes the
// pair of ports in .env.worktree and tmux-dev.sh exports them, so this config
// reads them from the environment. The main checkout keeps 5173 and 8000.
const backendPort = process.env.BACKEND_PORT || '8000'

// One vendor chunk per big library, so a change in app code does not
// invalidate the cached maplibre / deck.gl / vuetify bundles.
const vendorChunks: Record<string, RegExp> = {
  maplibre: /[\\/]node_modules[\\/](maplibre-gl|pmtiles)[\\/]/,
  deck: /[\\/]node_modules[\\/](@deck\.gl|@luma\.gl|@loaders\.gl|@math\.gl|@probe\.gl)[\\/]/,
  vuetify: /[\\/]node_modules[\\/]vuetify[\\/]/,
  d3: /[\\/]node_modules[\\/](d3-[a-z-]+|internmap)[\\/]/
}

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
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  css: {
    preprocessorOptions: {
      scss: { api: 'modern-compiler' }
    }
  },
  build: {
    // .map files are emitted but not referenced from the bundles
    sourcemap: 'hidden',
    rollupOptions: {
      output: {
        manualChunks(id) {
          for (const [name, pattern] of Object.entries(vendorChunks)) {
            if (pattern.test(id)) return name
          }
        }
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
