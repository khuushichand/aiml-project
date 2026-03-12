import { expect, test } from './helpers/fixtures';

test('multi-user admin login reaches dashboard', async ({ loginPage }) => {
  await loginPage.gotoJwtLogin();
  await loginPage.loginWithPassword('admin', 'AdminPass123!');
  await expect(loginPage.page).toHaveURL(/\/(?:$|\?)/);
});
