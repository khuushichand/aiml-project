import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    root: '.',
    include: ['tests/unit/**/*.spec.js'],
    restoreMocks: true,
    clearMocks: true,
    mockReset: true
  }
});
