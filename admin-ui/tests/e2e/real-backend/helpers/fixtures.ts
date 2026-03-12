import { expect, test as base } from '@playwright/test';

import { LoginPage } from './login-page';
import { getProjectEnv, type RealBackendProjectEnv } from './project-env';
import { SeededSession } from './session';

type RealBackendFixtures = {
  projectEnv: RealBackendProjectEnv;
  loginPage: LoginPage;
  seededSession: SeededSession;
  seedScenario: (scenario: 'jwt_admin' | 'dsr_jwt_admin') => Promise<void>;
};

export const test = base.extend<RealBackendFixtures>({
  projectEnv: async ({}, provide, testInfo) => {
    await provide(getProjectEnv(testInfo.project.name));
  },
  loginPage: async ({ page }, provide) => {
    await provide(new LoginPage(page));
  },
  seededSession: async ({ page, projectEnv }, provide) => {
    await provide(new SeededSession(page.context(), projectEnv));
  },
  seedScenario: async ({ seededSession }, provide) => {
    await provide(async (scenario) => {
      await seededSession.seed(scenario);
    });
  },
});

export { expect };
