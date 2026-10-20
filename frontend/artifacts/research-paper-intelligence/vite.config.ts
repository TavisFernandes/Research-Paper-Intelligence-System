import path from 'path';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

// Works locally and on Vercel without special environment variables:
//   PORT / BASE_PATH are optional (defaults 5173 and "/"); VITE_API_BASE_URL is the backend origin
//   used by the browser build (empty = same origin) and by the dev-server /api proxy.
const port = Number(process.env.PORT ?? 5173);
const basePath = process.env.BASE_PATH ?? '/';

export default defineConfig({
  base: basePath,
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, 'src') },
    dedupe: ['react', 'react-dom'],
  },
  root: path.resolve(import.meta.dirname),
  build: { outDir: path.resolve(import.meta.dirname, 'dist/public'), emptyOutDir: true },
  server: {
    port,
    strictPort: false,
    host: '0.0.0.0',
    proxy: { '/api': { target: process.env.VITE_API_BASE_URL || 'http://localhost:8000', changeOrigin: true } },
  },
  preview: { port, host: '0.0.0.0' },
});
