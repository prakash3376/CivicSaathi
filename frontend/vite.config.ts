import { fileURLToPath, URL } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { loadEnv } from 'vite'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // The empty prefix also loads variables without VITE_, which stay on the dev server
  // and are never exposed to browser code.
  const env = loadEnv(mode, process.cwd(), '')

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
    },
    server: {
      // The browser calls /api on the dev server's own origin, so no CORS is involved.
      proxy: {
        '/api': {
          target: env.API_PROXY_TARGET || 'http://127.0.0.1:8000',
          changeOrigin: true,
        },
      },
    },
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
      // The page tests render whole pages in jsdom and some run axe over several of them: the
      // slowest takes about 5 s alone, so the default 5 s limit failed whenever the machine was
      // busy (a dev server running, 22 workers at once). No test asserts on speed; this only
      // stops a slow machine from reporting a working page as broken.
      testTimeout: 30_000,
    },
  }
})
