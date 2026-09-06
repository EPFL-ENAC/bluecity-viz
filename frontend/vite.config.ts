import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vuetify from 'vite-plugin-vuetify'

// https://vitejs.dev/config/
// Git worktrees run one backend and one vite per branch. wt-setup.sh writes the
// pair of ports in .env.worktree and tmux-dev.sh exports them, so this config
// reads them from the environment. The main checkout keeps 5173 and 8000.
const backendPort = process.env.BACKEND_PORT || '8000'

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

      //  UNCOMMENT THIS IF YOURE HUGO
      // '^/geodata.*': {  // ADD THIS
      //   target: 'http://127.0.0.1:8000/data',
      //   changeOrigin: true,
      //   rewrite: (path) => path.replace(/^\/geodata/, '')
      // }
    }
  },
  plugins: [vue(), vuetify()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  }
})
