import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'WrangLED Command Center',
        short_name: 'WrangLED',
        description: 'LED control dashboard',
        theme_color: '#0b0e18',
        background_color: '#0b0e18',
        display: 'standalone',
        orientation: 'portrait',
        icons: [
          { src: '/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icon-512.png', sizes: '512x512', type: 'image/png' },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,png,svg,ico}'],
        navigateFallback: '/index.html',
        runtimeCaching: [
          { urlPattern: /^\/api\//, handler: 'NetworkOnly' },
        ],
      },
    }),
  ],
  build: {
    outDir: '../api/static/dashboard',
    emptyOutDir: true,
  },
  server: {
    port: 8510,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8500',
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            if (proxyRes.headers['content-type']?.includes('text/event-stream')) {
              proxyRes.headers['cache-control'] = 'no-cache';
              proxyRes.headers['connection'] = 'keep-alive';
            }
          });
        },
      },
      '/healthz': 'http://localhost:8500',
    },
  },
});
