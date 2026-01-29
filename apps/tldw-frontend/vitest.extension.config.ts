import { defineConfig } from 'vitest/config'
import path from 'path'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@tldw/ui': path.resolve(__dirname, '../packages/ui/src'),
      '@': path.resolve(__dirname, '../packages/ui/src'),
      '~': path.resolve(__dirname, '../packages/ui/src')
    }
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./vitest.extension.setup.ts'],
    include: ['../packages/ui/src/**/__tests__/**/*.{test,spec}.{ts,tsx}'],
    exclude: ['node_modules/**', 'dist/**', 'build/**']
  }
})
