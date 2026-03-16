import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://backend:8000',
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
})
