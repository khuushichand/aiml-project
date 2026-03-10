import { defineConfig, devices } from '@playwright/test';

const rawBaseUrl = process.env.TLDW_ADMIN_UI_URL || 'http://127.0.0.1:3001';
const baseURL = rawBaseUrl.replace('localhost', '127.0.0.1');
const webCommand = process.env.TLDW_ADMIN_UI_CMD || 'bun run dev -- --hostname 127.0.0.1';
const shouldAutoStart = process.env.TLDW_ADMIN_UI_AUTOSTART !== 'false';

export default defineConfig({
  testDir: 'tests/e2e',
  timeout: 60_000,
  expect: {
    timeout: 15_000,
  },
  retries: process.env.CI ? 2 : 0,
  reporter: 'line',
  outputDir: '/tmp/tldw-admin-playwright',
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
        env: {
          ...process.env,
          JWT_ALGORITHM: process.env.JWT_ALGORITHM || 'HS256',
          JWT_SECRET_KEY: process.env.JWT_SECRET_KEY || 'playwright-test-secret',
          NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:5999',
          NEXT_TELEMETRY_DISABLED: '1',
        },
      }
    : undefined,
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
