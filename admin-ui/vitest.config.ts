import { configDefaults, defineConfig } from 'vitest/config';
import path from 'path';

export default defineConfig({
  esbuild: {
    jsx: 'automatic',
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, '.'),
    },
  },
  test: {
    environment: 'jsdom',
    exclude: [...configDefaults.exclude, 'tests/e2e/**'],
    setupFiles: ['./vitest.setup.ts'],
  },
});
