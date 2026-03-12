import { expect, test } from '@playwright/test';
import { installAdminApiRoutes, setAuthenticatedSession } from './smoke-helpers';

test('requires reason and reauthentication before reset password', async ({ page }) => {
  await installAdminApiRoutes(page);
  await setAuthenticatedSession(page);

  await page.goto('/users/42');
  await page.getByLabel(/temporary password to set/i).fill('TempP@ssw0rd123');
  await page.getByRole('button', { name: /reset password/i }).click();

  await expect(page.getByLabel(/reason/i)).toBeVisible();
  await expect(page.getByLabel(/current password/i)).toBeVisible();
});
