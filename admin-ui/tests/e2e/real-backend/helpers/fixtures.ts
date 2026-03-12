import { expect, test as base, type Page } from '@playwright/test';

class LoginPage {
  constructor(readonly page: Page) {}

  async gotoJwtLogin(): Promise<void> {
    await this.page.goto('/login');
  }

  async gotoSingleUserLogin(redirectTo: string): Promise<void> {
    await this.page.goto(`/login?redirectTo=${encodeURIComponent(redirectTo)}&mode=apikey`);
  }

  async loginWithPassword(username: string, password: string): Promise<void> {
    await this.page.getByLabel(/username or email/i).fill(username);
    await this.page.getByLabel(/^password$/i).fill(password);
    await this.page.getByRole('button', { name: /sign in/i }).click();
  }

  async loginWithApiKey(apiKey: string): Promise<void> {
    await this.page.getByRole('tab', { name: /api key/i }).click();
    await this.page.locator('#apiKey').fill(apiKey);
    await this.page.getByRole('button', { name: /connect with api key/i }).click();
  }
}

type RealBackendFixtures = {
  loginPage: LoginPage;
};

export const test = base.extend<RealBackendFixtures>({
  loginPage: async ({ page }, provide) => {
    await provide(new LoginPage(page));
  },
});

export { expect };
