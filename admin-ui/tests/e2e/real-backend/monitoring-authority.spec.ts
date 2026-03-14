import { expect, test } from './helpers/fixtures';
import { postAdminE2EJson } from './helpers/admin-e2e-support';

test.describe.configure({ mode: 'serial' });

test('monitoring rule and alert assignment persist across reload', async ({ monitoringPage, projectEnv, seededSession }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-real-jwt', 'Monitoring authority coverage only runs in the multi-user JWT project');

  await postAdminE2EJson(projectEnv.apiBaseUrl, '/api/v1/test-support/admin-e2e/reset');
  const seed = await seededSession.as('admin', 'jwt_admin');
  const alertFixture = seed.fixtures.alerts[0];

  await monitoringPage.goto();
  await monitoringPage.expectReady();

  await monitoringPage.createRule({ threshold: '91.25', durationMinutes: '15', severity: 'critical' });
  await monitoringPage.expectRulePresent('91.25');

  await monitoringPage.assignAlert(alertFixture.alert_id, String(seed.users.admin.id));
  await monitoringPage.expectAlertAssigned(alertFixture.alert_id, String(seed.users.admin.id));
  await monitoringPage.expectHistoryContains(`Assigned to user ${seed.users.admin.id}`);

  await monitoringPage.reload();
  await monitoringPage.expectRulePresent('91.25');
  await monitoringPage.expectAlertAssigned(alertFixture.alert_id, String(seed.users.admin.id));
  await monitoringPage.expectHistoryContains(`Assigned to user ${seed.users.admin.id}`);
});

test('non-admin users are denied from the monitoring route', async ({ monitoringPage, projectEnv, seededSession }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-real-jwt', 'Monitoring authority coverage only runs in the multi-user JWT project');

  await postAdminE2EJson(projectEnv.apiBaseUrl, '/api/v1/test-support/admin-e2e/reset');
  await seededSession.as('non_admin', 'jwt_admin');

  await monitoringPage.goto();
  await monitoringPage.expectDenied();
  await expect(monitoringPage.page.getByRole('heading', { name: /alert rules/i })).toHaveCount(0);
});
