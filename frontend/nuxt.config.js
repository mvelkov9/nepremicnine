import { fileURLToPath } from 'node:url'

const local = (path) => fileURLToPath(new URL(path, import.meta.url))

export default defineNuxtConfig({
  compatibilityDate: '2025-01-01',
  devtools: { enabled: false },
  buildDir: process.env.NUXT_BUILD_DIR || '.nuxt-local',
  modules: ['@nuxt/ui', '@pinia/nuxt'],
  css: ['~/assets/css/app.css', 'leaflet/dist/leaflet.css'],
  fonts: {
    provider: 'local',
  },
  colorMode: {
    classSuffix: '',
    preference: 'system',
    fallback: 'light',
  },
  runtimeConfig: {
    backendUrl: process.env.BACKEND_URL || 'http://localhost:8000',
    public: {
      appVersion: process.env.APP_VERSION || '0.11.0',
    },
  },
  nitro: {
    output: {
      dir: process.env.NUXT_OUTPUT_DIR || '.output-local',
    },
  },
  vite: {
    cacheDir: process.env.VITE_CACHE_DIR || '.vite-cache',
    resolve: {
      alias: {
        'primevue/autocomplete': local('./components/primevue/AutoComplete.vue'),
        'primevue/button': local('./components/primevue/Button.vue'),
        'primevue/card': local('./components/primevue/Card.vue'),
        'primevue/checkbox': local('./components/primevue/Checkbox.vue'),
        'primevue/column': local('./components/primevue/Column.vue'),
        'primevue/datatable': local('./components/primevue/DataTable.vue'),
        'primevue/dialog': local('./components/primevue/Dialog.vue'),
        'primevue/inputnumber': local('./components/primevue/InputNumber.vue'),
        'primevue/inputtext': local('./components/primevue/InputText.vue'),
        'primevue/progressbar': local('./components/primevue/ProgressBar.vue'),
        'primevue/select': local('./components/primevue/Select.vue'),
        'primevue/selectbutton': local('./components/primevue/SelectButton.vue'),
        'primevue/tag': local('./components/primevue/Tag.vue'),
        'primevue/textarea': local('./components/primevue/Textarea.vue'),
        'primevue/toggleswitch': local('./components/primevue/ToggleSwitch.vue'),
        'primevue/tooltip': local('./components/primevue/tooltip.js'),
      },
    },
  },
})
