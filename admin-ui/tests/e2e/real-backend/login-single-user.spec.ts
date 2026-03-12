import { expect, test } from './helpers/fixtures';

test('single-user API-key login reaches debug redirect target', async ({ loginPage, seedScenario }, testInfo) => {
  test.skip(
    testInfo.project.name !== 'chromium-real-single-user',
    'API-key login smoke only runs in the single-user project',
  );
  const seed = await seedScenario('single_user_admin');
  await loginPage.gotoSingleUserLogin('/debug');
  await loginPage.loginWithApiKey(seed.users.admin.key);
  await expect(loginPage.page).toHaveURL(/\/debug/);
  await expect(loginPage.page.getByRole('heading', { name: /debug tools/i })).toBeVisible();
});
