import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      recharts: fileURLToPath(new URL('./src/components/charts/Recharts.tsx', import.meta.url)),
      'react-router-dom': fileURLToPath(new URL('./src/components/router/Router.tsx', import.meta.url)),
    },
  },
  server: { port: 5173 },
  preview: { port: 4173 },
  build: {
    sourcemap: false,
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        entryFileNames: 'assets/[name]-[hash].js',
        chunkFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash][extname]'
      }
    }
  }
});
