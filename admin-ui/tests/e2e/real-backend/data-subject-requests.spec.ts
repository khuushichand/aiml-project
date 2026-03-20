import { expect, test } from './helpers/fixtures';

test('records a DSR access request and survives reload', async ({ dsrPage, seededSession }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-real-jwt', 'DSR browser coverage only runs in the multi-user JWT project');

  const seed = await seededSession.as('admin', 'dsr_jwt_admin');
  await dsrPage.goto();
  await dsrPage.submitAccessRequest(seed.users.requester.email);
  await dsrPage.expectAccessSummary();
  await dsrPage.expectRecordedRow(seed.users.requester.email, 'recorded');

  await dsrPage.reload();
  await dsrPage.expectRecordedRow(seed.users.requester.email, 'recorded');
});

test('unknown requester fails closed without a fake history row', async ({ dsrPage, seededSession }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-real-jwt', 'DSR browser coverage only runs in the multi-user JWT project');

  await seededSession.as('admin', 'dsr_jwt_admin');
  await dsrPage.goto();

  await dsrPage.submitAccessRequest('missing-requester@example.local');
  await dsrPage.expectRequestFailure(/requester_not_found/i);
  await dsrPage.expectNoRecordedRow('missing-requester@example.local');

  await dsrPage.reload();
  await dsrPage.expectNoRecordedRow('missing-requester@example.local');
  await expect(dsrPage.page.getByTestId('dsr-access-summary')).toHaveCount(0);
});
