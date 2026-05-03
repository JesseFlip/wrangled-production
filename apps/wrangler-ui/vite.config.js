import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 8511,
    strictPort: true,
    proxy: {
      '/api': 'http://localhost:8501',
      '/healthz': 'http://localhost:8501',
    },
  },
});
