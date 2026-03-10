import { expect, test } from '@playwright/test';
import { installAdminApiRoutes, installLoginRoutes } from './smoke-helpers';

test('supports password login and MFA challenge completion', async ({ page }) => {
  await installAdminApiRoutes(page);
  await installLoginRoutes(page);

  await page.goto('/login?redirectTo=%2Fusers%2F42');
  await page.getByLabel(/username or email/i).fill('admin');
  await page.getByLabel(/^password$/i).fill('AdminPass123!');
  await page.getByRole('button', { name: /sign in/i }).click();

  await expect(page.getByLabel(/verification code/i)).toBeVisible();
  await page.getByLabel(/verification code/i).fill('123456');
  await page.getByRole('button', { name: /verify mfa/i }).click();

  await expect(page).toHaveURL(/\/users\/42$/);
  await expect(page.getByRole('button', { name: 'Reset Password' })).toBeVisible();
});
