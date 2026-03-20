import { expect, test as base } from '@playwright/test';

import { BackupsPage } from './page-objects/backups-page';
import { DataSubjectRequestsPage } from './page-objects/data-subject-requests-page';
import { DebugPage } from './page-objects/debug-page';
import { MonitoringPage } from './page-objects/monitoring-page';
import { LoginPage } from './login-page';
import { getProjectEnv, type RealBackendProjectEnv } from './project-env';
import { SeededSession, type SeedResponse, type SeedScenario } from './session';

type RealBackendFixtures = {
  projectEnv: RealBackendProjectEnv;
  loginPage: LoginPage;
  backupsPage: BackupsPage;
  dsrPage: DataSubjectRequestsPage;
  monitoringPage: MonitoringPage;
  debugPage: DebugPage;
  seededSession: SeededSession;
  seedScenario: (scenario: SeedScenario) => Promise<SeedResponse>;
};

export const test = base.extend<RealBackendFixtures>({
  projectEnv: async ({}, provide, testInfo) => {
    await provide(getProjectEnv(testInfo.project.name));
  },
  loginPage: async ({ page }, provide) => {
    await provide(new LoginPage(page));
  },
  backupsPage: async ({ page }, provide) => {
    await provide(new BackupsPage(page));
  },
  dsrPage: async ({ page }, provide) => {
    await provide(new DataSubjectRequestsPage(page));
  },
  monitoringPage: async ({ page }, provide) => {
    await provide(new MonitoringPage(page));
  },
  debugPage: async ({ page }, provide) => {
    await provide(new DebugPage(page));
  },
  seededSession: async ({ page, projectEnv }, provide) => {
    await provide(new SeededSession(page, projectEnv));
  },
  seedScenario: async ({ seededSession }, provide) => {
    await provide(async (scenario) => {
      return seededSession.seed(scenario);
    });
  },
});

export { expect };
