import { defineConfig } from 'vitest/config'
import path from 'path'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'extension'),
      '~': path.resolve(__dirname, 'extension')
    }
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./vitest.extension.setup.ts'],
    include: ['extension/**/__tests__/**/*.{test,spec}.{ts,tsx}'],
    exclude: ['node_modules/**', 'dist/**', 'build/**']
  }
})
