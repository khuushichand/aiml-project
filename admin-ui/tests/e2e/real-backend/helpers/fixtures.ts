import { expect, test as base } from '@playwright/test';

import { DataSubjectRequestsPage } from './page-objects/data-subject-requests-page';
import { LoginPage } from './login-page';
import { getProjectEnv, type RealBackendProjectEnv } from './project-env';
import { SeededSession, type SeedResponse } from './session';

type RealBackendFixtures = {
  projectEnv: RealBackendProjectEnv;
  loginPage: LoginPage;
  dsrPage: DataSubjectRequestsPage;
  seededSession: SeededSession;
  seedScenario: (scenario: 'jwt_admin' | 'dsr_jwt_admin') => Promise<SeedResponse>;
};

export const test = base.extend<RealBackendFixtures>({
  projectEnv: async ({}, provide, testInfo) => {
    await provide(getProjectEnv(testInfo.project.name));
  },
  loginPage: async ({ page }, provide) => {
    await provide(new LoginPage(page));
  },
  dsrPage: async ({ page }, provide) => {
    await provide(new DataSubjectRequestsPage(page));
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
