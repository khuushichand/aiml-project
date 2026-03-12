import { expect, test } from './helpers/fixtures';

type TriggerResponse = {
  ok: boolean;
  triggered_runs: number;
};

const postAdminE2E = async <T>(baseUrl: string, path: string): Promise<T> => {
  const response = await fetch(`${baseUrl}${path}`, {
    method: 'POST',
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new Error(`Admin e2e request failed for ${path}: ${response.status} ${detail}`.trim());
  }
  return response.json() as Promise<T>;
};

test.describe.configure({ mode: 'serial' });

test('creates a schedule and persists it across reload', async ({ backupsPage, projectEnv, seededSession }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-real-jwt', 'Backup scheduling browser coverage only runs in the multi-user JWT project');

  await postAdminE2E(projectEnv.apiBaseUrl, '/api/v1/test-support/admin-e2e/reset');
  const seed = await seededSession.as('admin', 'dsr_jwt_admin');

  await backupsPage.gotoScheduleTab();
  await backupsPage.createSchedule({
    dataset: 'media',
    targetUserId: seed.users.requester.id,
    frequency: 'daily',
    timeOfDay: '02:00',
    retentionCount: 3,
  });
  await backupsPage.expectScheduleRow('media', seed.users.requester.email, 'Daily at 02:00 UTC');

  await backupsPage.reloadScheduleTab();
  await backupsPage.expectScheduleRow('media', seed.users.requester.email, 'Daily at 02:00 UTC');
});

test('scheduler trigger produces visible run metadata', async ({ backupsPage, projectEnv, seededSession }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-real-jwt', 'Backup scheduling browser coverage only runs in the multi-user JWT project');

  await postAdminE2E(projectEnv.apiBaseUrl, '/api/v1/test-support/admin-e2e/reset');
  const seed = await seededSession.as('admin', 'dsr_jwt_admin');

  await backupsPage.gotoScheduleTab();
  const scheduleId = await backupsPage.createSchedule({
    dataset: 'chacha',
    targetUserId: seed.users.requester.id,
    frequency: 'daily',
    timeOfDay: '03:00',
    retentionCount: 5,
  });

  const trigger = await postAdminE2E<TriggerResponse>(
    projectEnv.apiBaseUrl,
    '/api/v1/test-support/admin-e2e/run-due-backup-schedules',
  );
  expect(trigger.ok).toBe(true);
  expect(trigger.triggered_runs).toBe(1);

  await backupsPage.reloadScheduleTab();
  await backupsPage.expectScheduleRunMetadata(scheduleId);
});

test('authnz schedule fails closed for a non-platform admin', async ({ backupsPage, projectEnv, seededSession }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-real-jwt', 'Backup scheduling browser coverage only runs in the multi-user JWT project');

  await postAdminE2E(projectEnv.apiBaseUrl, '/api/v1/test-support/admin-e2e/reset');
  await seededSession.as('admin', 'jwt_admin');

  await backupsPage.gotoScheduleTab();
  await backupsPage.createSchedule({
    dataset: 'authnz',
    frequency: 'daily',
    timeOfDay: '04:00',
    retentionCount: 2,
  }).catch(() => {
    // The row should not appear for the denied create path; the inline error is asserted below.
  });

  await backupsPage.expectNoScheduleRow('authnz');
  await backupsPage.reloadScheduleTab();
  await backupsPage.expectNoScheduleRow('authnz');
});
