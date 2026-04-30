import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// Build output goes into Flask's static folder so /dashboard can serve it.
// We keep `assetsDir = 'assets'` and `base = '/static/dashboard-v2/'` so all
// asset URLs in the built index.html resolve correctly under Flask.
export default defineConfig({
  plugins: [vue()],
  base: '/static/dashboard-v2/',
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    outDir: '../static/dashboard-v2',
    emptyOutDir: true,
    sourcemap: false,
    target: 'es2020',
  },
  server: {
    port: 5173,
    proxy: {
      // During `npm run dev`, proxy API calls to Flask on :5000
      '/api': 'http://localhost:5000',
      '/static': 'http://localhost:5000',
    },
  },
})
