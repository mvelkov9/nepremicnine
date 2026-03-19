import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import Components from 'unplugin-vue-components/vite'
import AutoImport from 'unplugin-auto-import/vite'
import { PrimeVueResolver } from '@primevue/auto-import-resolver'
import { fileURLToPath } from 'node:url'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendUrl = env.VITE_API_URL || 'http://localhost:8000'

  return {
    plugins: [
      vue(),
      tailwindcss(),
      // Auto-import PrimeVue components — eliminates individual import lines per view
      Components({
        resolvers: [PrimeVueResolver()],
        dts: 'src/types/components.d.ts',
      }),
      // Auto-import Vue, Vue Router, Pinia, and VueUse APIs
      AutoImport({
        imports: ['vue', 'vue-router', 'pinia', '@vueuse/core'],
        dts: 'src/types/auto-imports.d.ts',
        vueTemplate: true,
      }),
    ],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    build: {
      chunkSizeWarningLimit: 600,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (['vue', 'vue-router', 'pinia', 'vue-i18n'].some(pkg => id.includes(`/node_modules/${pkg}/`) || id.includes(`/node_modules/.pnpm/${pkg}`))) return 'vendor'
            if (id.includes('/node_modules/primevue/') || id.includes('/node_modules/.pnpm/primevue')) return 'primevue'
            if (id.includes('/node_modules/@vueuse/') || id.includes('/node_modules/.pnpm/@vueuse')) return 'vueuse'
          },
        },
      },
    },
    server: {
      host: '0.0.0.0',
      port: 5173,
      proxy: {
        '/api': {
          target: backendUrl,
          changeOrigin: true,
          configure: (proxy) => {
            // Allow large file uploads (default is ~1 MB)
            proxy.on('proxyReq', (proxyReq, req) => {
              const contentLength = req.headers['content-length']
              if (contentLength) {
                proxyReq.setHeader('content-length', contentLength)
              }
            })
          },
        },
      },
    },
  }
})
