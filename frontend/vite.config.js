import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiProxyTarget = env.VITE_API_PROXY_TARGET || 'http://localhost:8000'

  return {
    plugins: [vue(), tailwindcss()],
    build: {
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (!id.includes('node_modules')) {
              return undefined
            }

            if (id.includes('leaflet')) {
              return 'vendor-map'
            }

            if (id.includes('chart.js') || id.includes('vue-chartjs')) {
              return 'vendor-charts'
            }

            if (id.includes('primevue/datatable') || id.includes('primevue/column')) {
              return 'prime-data'
            }

            if (
              id.includes('primevue/select') ||
              id.includes('primevue/inputnumber') ||
              id.includes('primevue/inputtext') ||
              id.includes('primevue/textarea') ||
              id.includes('primevue/toggleswitch') ||
              id.includes('primevue/button') ||
              id.includes('primevue/tag') ||
              id.includes('primevue/progressbar') ||
              id.includes('primevue/autocomplete') ||
              id.includes('primevue/toast') ||
              id.includes('primevue/confirmdialog')
            ) {
              return 'prime-ui'
            }

            if (
              id.includes('/vue/') ||
              id.includes('pinia') ||
              id.includes('vue-router') ||
              id.includes('vue-i18n')
            ) {
              return 'vendor-core'
            }

            if (id.includes('axios') || id.includes('@vueuse/core')) {
              return 'vendor-utils'
            }

            return 'vendor-misc'
          },
        },
      },
    },
    server: {
      host: '0.0.0.0',
      port: 5173,
      proxy: {
        '/api': {
          target: apiProxyTarget,
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
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: './src/test/setup.js',
    },
  }
})
