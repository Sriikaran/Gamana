import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    allowedHosts: true, // Allow Cloudflare/Ngrok tunnels
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      '/video_feed': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      '/upload': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      '/backend': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/backend/, '')
      }
    },
  },
})
