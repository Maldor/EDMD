// Compatible with Vite 5, 6, 7, 8 — uses only stable core config APIs
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import path from 'path';

export default defineConfig({
  plugins: [vue()],
  root:    '.',
  base:    './',
  build: {
    outDir:      'dist',
    emptyOutDir: true,
    sourcemap:   false,
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    port:       5173,
    strictPort: true,
  },
});
