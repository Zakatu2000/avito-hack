import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: process.env.VITE_PROXY_TARGET ?? 'http://127.0.0.1:5050',
        changeOrigin: true,
      },
      '/demo': { target: process.env.VITE_PROXY_TARGET ?? 'http://127.0.0.1:5050', changeOrigin: true },
    },
  },
  test: {
    include: ['src/**/*.test.{ts,tsx}'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/**/*.test.*', 'src/test/**', 'src/**/*.d.ts'],
    },
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
});
