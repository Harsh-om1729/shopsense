/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    // Forward /api to FastAPI, so the browser sees one address during development.
    // Set SHOPSENSE_API_URL if the API runs somewhere other than port 8000.
    proxy: {
      '/api': {
        target: process.env.SHOPSENSE_API_URL ?? 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  test: {
    environment: 'jsdom',
    // Browser tests in e2e/ run under Playwright, not Vitest.
    include: ['src/**/*.test.{ts,tsx}'],
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})
