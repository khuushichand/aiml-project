import { test } from './helpers/fixtures';

test.describe.configure({ mode: 'serial' });

test('multi-user owner can access debug tools', async ({ debugPage, seededSession }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-real-jwt', 'Multi-user debug RBAC coverage only runs in the JWT project');

  await seededSession.as('owner', 'jwt_admin');
  await debugPage.goto();
  await debugPage.expectAllowed();
});

test('plain multi-user admin is denied from debug tools', async ({ debugPage, seededSession }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-real-jwt', 'Multi-user debug RBAC coverage only runs in the JWT project');

  await seededSession.as('admin', 'jwt_admin');
  await debugPage.goto();
  await debugPage.expectDenied();
});
