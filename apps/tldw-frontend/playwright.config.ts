import { defineConfig, devices } from '@playwright/test';

const rawBaseUrl = process.env.TLDW_WEB_URL || 'http://localhost:8080';
const baseURL = rawBaseUrl.replace('127.0.0.1', 'localhost');
const webCommand = process.env.TLDW_WEB_CMD || 'bun run dev -- -p 8080';
const shouldAutoStart = process.env.TLDW_WEB_AUTOSTART !== 'false';

export default defineConfig({
  testDir: 'e2e',
  timeout: 60_000,
  expect: {
    timeout: 15_000,
  },
  retries: process.env.CI ? 2 : 0,
  use: {
    baseURL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  webServer: shouldAutoStart
    ? {
        command: webCommand,
        url: baseURL,
        reuseExistingServer: true,
        timeout: 120_000,
      }
    : undefined,
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
