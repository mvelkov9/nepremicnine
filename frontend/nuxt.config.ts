export default defineNuxtConfig({
  compatibilityDate: '2025-01-01',
  devtools: { enabled: false },
  buildDir: process.env.NUXT_BUILD_DIR || '.nuxt-dev',

  modules: ['@nuxt/ui', '@pinia/nuxt', '@vueuse/nuxt', '@nuxtjs/i18n'],

  css: ['~/assets/css/app.css', 'leaflet/dist/leaflet.css'],

  ui: {
    fonts: false,
  },

  colorMode: {
    classSuffix: '',
    preference: 'system',
    fallback: 'light',
  },

  i18n: {
    locales: [
      { code: 'sl', language: 'sl-SI', file: 'sl.json', name: 'Slovenščina' },
      { code: 'en', language: 'en-US', file: 'en.json', name: 'English' },
    ],
    defaultLocale: 'sl',
    langDir: 'locales',
    strategy: 'no_prefix',
    detectBrowserLanguage: {
      useCookie: true,
      cookieKey: 'i18n_redirected',
      fallbackLocale: 'sl',
    },
  },

  runtimeConfig: {
    backendUrl: process.env.BACKEND_URL || 'http://localhost:8000',
    public: {
      appVersion: process.env.APP_VERSION || '0.12.0',
    },
  },

  nitro: {
    output: {
      dir: process.env.NUXT_OUTPUT_DIR || '.output-dev',
    },
  },

  vite: {
    cacheDir: process.env.VITE_CACHE_DIR || '.vite-cache',
    optimizeDeps: {
      include: ['leaflet'],
    },
    server: {
      watch: {
        ignored: [
          '**/.nuxt-app/**',
          '**/.nuxt-build/**',
          '**/.nuxt-local/**',
          '**/.nuxt-preview/**',
          '**/.nuxt-typecheck/**',
          '**/.nuxt-verify/**',
          '**/.output/**',
          '**/.output-build/**',
          '**/.output-local/**',
          '**/.output-typecheck/**',
          '**/.output-verify/**',
        ],
      },
    },
  },
})
