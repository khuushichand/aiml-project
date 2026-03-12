import { expect, test } from '@playwright/test';
import {
  installAdminApiRoutes,
  singleUserApiKey,
  startSingleUserBackendStub,
} from './smoke-helpers';

test('allows a single-user admin session to reach debug tools', async ({ page }) => {
  const stopBackendStub = await startSingleUserBackendStub();
  await installAdminApiRoutes(page);

  try {
    await page.goto('/login?redirectTo=%2Fdebug');
    await page.getByRole('tab', { name: 'API Key' }).click();
    await page.locator('#apiKey').fill(singleUserApiKey);
    await page.getByRole('button', { name: /connect with api key/i }).click();

    await expect(page).toHaveURL(/\/debug$/);
    await expect(page.getByRole('heading', { name: 'Debug Tools' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Debug' })).toBeVisible();
  } finally {
    await stopBackendStub();
  }
});
