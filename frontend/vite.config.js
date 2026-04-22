import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import Components from 'unplugin-vue-components/vite'
import AutoImport from 'unplugin-auto-import/vite'
import { PrimeVueResolver } from '@primevue/auto-import-resolver'
import { fileURLToPath } from 'node:url'

const primeVueOptimizeDeps = [
  'primevue/autocomplete',
  'primevue/button',
  'primevue/column',
  'primevue/config',
  'primevue/confirmationservice',
  'primevue/confirmdialog',
  'primevue/datatable',
  'primevue/dialog',
  'primevue/drawer',
  'primevue/fileupload',
  'primevue/iconfield',
  'primevue/inputicon',
  'primevue/inputnumber',
  'primevue/inputtext',
  'primevue/menu',
  'primevue/paginator',
  'primevue/password',
  'primevue/progressbar',
  'primevue/select',
  'primevue/selectbutton',
  'primevue/skeleton',
  'primevue/slider',
  'primevue/tab',
  'primevue/tablist',
  'primevue/tabpanel',
  'primevue/tabpanels',
  'primevue/tabs',
  'primevue/tag',
  'primevue/textarea',
  'primevue/timeline',
  'primevue/toast',
  'primevue/toastservice',
  'primevue/toggleswitch',
  'primevue/tooltip',
  'primevue/useconfirm',
  'primevue/usetoast',
]

const appOptimizeDeps = [
  'vue',
  'vue-router',
  'pinia',
  'vue-i18n',
  '@vueuse/core',
  'axios',
  '@primeuix/themes',
  '@primeuix/themes/aura',
  'chart.js',
  'vue-chartjs',
  'leaflet',
  ...primeVueOptimizeDeps,
]

function packageInPath(id, pkg) {
  return id.includes(`/node_modules/${pkg}/`) || id.includes(`/node_modules/.pnpm/${pkg}`)
}

function getPrimeVueChunk(id) {
  if (!packageInPath(id, 'primevue')) return null

  if (/primevue\/(datatable|column|treetable|tree|paginator)/.test(id)) {
    return 'primevue-data'
  }

  if (/primevue\/(dialog|drawer|popover|tooltip|toast|confirmpopup|confirmdialog|menu)/.test(id)) {
    return 'primevue-overlay'
  }

  if (
    /primevue\/(inputtext|inputnumber|autocomplete|textarea|password|select|selectbutton|toggleswitch|checkbox|radiobutton|datepicker)/.test(
      id,
    )
  ) {
    return 'primevue-forms'
  }

  if (/primevue\/(button|tag|message|progressbar|skeleton|card|divider)/.test(id)) {
    return 'primevue-ui'
  }

  return 'primevue-core'
}

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
    optimizeDeps: {
      // Prevent cold-start hash churn in dev when auto-imported PrimeVue modules
      // are discovered after the first route render.
      include: appOptimizeDeps,
    },
    build: {
      chunkSizeWarningLimit: 600,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (['vue', 'vue-router', 'pinia', 'vue-i18n'].some((pkg) => packageInPath(id, pkg))) {
              return 'vendor'
            }

            if (packageInPath(id, '@vueuse/core')) return 'vueuse'
            if (packageInPath(id, 'axios')) return 'network'
            if (packageInPath(id, 'leaflet')) return 'maps'
            if (packageInPath(id, 'chart.js') || packageInPath(id, 'vue-chartjs')) return 'charts'
            if (packageInPath(id, '@primeuix/themes')) return 'primevue-core'

            const primeVueChunk = getPrimeVueChunk(id)
            if (primeVueChunk) return primeVueChunk
          },
        },
      },
    },
    server: {
      host: '0.0.0.0',
      port: 5173,
      watch: {
        ignored: [
          '**/.pnpm-store/**',
          '**/node_modules/.cache/**',
          '**/playwright-report/**',
          '**/test-results/**',
          '**/coverage/**',
        ],
      },
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
