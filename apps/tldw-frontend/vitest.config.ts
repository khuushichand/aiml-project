import { defineConfig } from 'vitest/config';
import path from 'path';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@tldw/ui': path.resolve(__dirname, '../packages/ui/src'),
      '@': path.resolve(__dirname, '../packages/ui/src'),
      '~': path.resolve(__dirname, '../packages/ui/src'),
      '@web': path.resolve(__dirname, '.'),
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./vitest.setup.ts'],
    include: [
      '**/__tests__/**/*.test.{ts,tsx}',
      '**/__tests__/**/*.spec.{ts,tsx}',
    ],
    exclude: ['node_modules/**', 'dist/**', 'build/**', 'pages/**'],
  },
});
