/// <reference types="vitest/config" />
import path from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    globals: true,
    // e2e/ holds the Playwright suite (npm run test:e2e).
    include: ['src/**/*.test.{ts,tsx}'],
  },
  // `vite preview` serves the production build, which calls the API at
  // /_/backend exactly as it does on Vercel. Route that to a local backend so
  // the real bundle can be exercised end to end (npm run test:e2e).
  preview: {
    host: '127.0.0.1',
    port: 4173,
    strictPort: true,
    proxy: {
      '/_/backend': {
        target: `http://127.0.0.1:${process.env.E2E_API_PORT ?? 8010}`,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/_\/backend/, ''),
      },
    },
  },
  server: {
    host: true,
    port: 5173,
    strictPort: true,
    allowedHosts: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8010',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/socket.io': {
        target: 'http://127.0.0.1:3001',
        ws: true,
        changeOrigin: true,
      },
      '/media': {
        target: 'http://127.0.0.1:8010',
        changeOrigin: true,
      },
    },
  },
})
