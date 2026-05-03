import { defineConfig } from 'vite'

export default defineConfig({
  server: {
    host: '0.0.0.0',
    allowedHosts: ['jv-desktop', 'jv-desktop.local', 'localhost'],
  },
})
