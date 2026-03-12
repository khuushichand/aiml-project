import { expect, test } from './helpers/fixtures';

test('single-user API-key login reaches debug redirect target', async ({ loginPage }) => {
  await loginPage.gotoSingleUserLogin('/debug');
  await loginPage.loginWithApiKey('single-user-admin-key');
  await expect(loginPage.page).toHaveURL(/\/debug/);
});
