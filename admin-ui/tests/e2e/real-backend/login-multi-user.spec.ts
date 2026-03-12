import { expect, test } from './helpers/fixtures';

test('multi-user admin login establishes an authenticated browser session', async ({ loginPage, seedScenario }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-real-jwt', 'JWT login smoke only runs in the multi-user project');
  await seedScenario('jwt_admin');
  await loginPage.gotoJwtLogin('/login?postAuthSmoke=1');
  await loginPage.loginWithPassword('admin', 'AdminPass123!');
  await expect(loginPage.page).toHaveURL(/\/login\?postAuthSmoke=1/);
  const currentUser = await loginPage.page.evaluate(async () => {
    const response = await fetch('/api/proxy/users/me', {
      credentials: 'include',
    });
    return {
      ok: response.ok,
      status: response.status,
      body: await response.json().catch(() => null),
    };
  });
  expect(currentUser.ok).toBe(true);
  expect(currentUser.body).toMatchObject({ username: 'admin', role: 'admin' });
});
