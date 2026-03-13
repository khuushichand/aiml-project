import { type Page } from '@playwright/test';

export class LoginPage {
  private redirectTarget = '/';

  constructor(readonly page: Page) {}

  private async waitForHydrated(): Promise<void> {
    await this.page.locator('body[data-login-hydrated="true"]').waitFor();
    await this.page.waitForTimeout(750);
    await this.page.locator('body[data-login-hydrated="true"]').waitFor();
  }

  private async submitAuthForm(
    endpoint: string,
    buttonName: RegExp,
    fillFields: () => Promise<void>,
  ): Promise<void> {
    const retryUrl = this.page.url();
    for (let attempt = 0; attempt < 3; attempt += 1) {
      await this.waitForHydrated();
      await fillFields();
      const responsePromise = this.page
        .waitForResponse(
          (response) =>
            response.url().includes(endpoint)
            && response.request().method() === 'POST',
          { timeout: 5_000 },
        )
        .catch(() => null);
      await this.page.getByRole('button', { name: buttonName }).click();
      const response = await responsePromise;
      if (response?.ok()) {
        await this.waitForPostAuthRedirect();
        return;
      }
      if (response && response.status() !== 404 && response.status() < 500) {
        const detail = (await response.text().catch(() => '')).trim();
        const backendUrl = response.headers()['x-tldw-backend-url'];
        throw new Error(
          `Authentication form ${endpoint} failed with status ${response.status()}`
          + `${backendUrl ? ` via ${backendUrl}` : ''}`
          + `${detail ? `: ${detail}` : ''}`,
        );
      }
      await this.page.goto(retryUrl);
      await this.page.waitForTimeout(1_000);
    }

    throw new Error(`Authentication form ${endpoint} did not complete successfully after retries`);
  }

  private async waitForPostAuthRedirect(): Promise<void> {
    const expectedUrl = this.redirectTarget;
    await this.page.waitForURL((url) => `${url.pathname}${url.search}` === expectedUrl, {
      timeout: 10_000,
    });
    await this.page.waitForLoadState('domcontentloaded');
  }

  async gotoJwtLogin(redirectTo = '/'): Promise<void> {
    const target = redirectTo === '/'
      ? '/login'
      : `/login?redirectTo=${encodeURIComponent(redirectTo)}`;
    this.redirectTarget = redirectTo;
    await this.page.goto(target);
    await this.waitForHydrated();
  }

  async gotoSingleUserLogin(redirectTo: string): Promise<void> {
    this.redirectTarget = redirectTo;
    await this.page.goto(`/login?redirectTo=${encodeURIComponent(redirectTo)}&mode=apikey`);
    await this.waitForHydrated();
  }

  async loginWithPassword(username: string, password: string): Promise<void> {
    await this.submitAuthForm('/api/auth/login', /sign in/i, async () => {
      await this.page.getByLabel(/username or email/i).fill(username);
      await this.page.getByLabel(/^password$/i).fill(password);
    });
  }

  async loginWithApiKey(apiKey: string): Promise<void> {
    await this.submitAuthForm('/api/auth/apikey', /connect with api key/i, async () => {
      await this.page.getByRole('tab', { name: /api key/i }).click();
      await this.page.locator('#apiKey').fill(apiKey);
    });
  }

  async waitForAuthenticatedSession(): Promise<void> {
    for (let attempt = 0; attempt < 20; attempt += 1) {
      const currentUser = await this.page.evaluate(async () => {
        try {
          const response = await fetch('/api/proxy/users/me', {
            credentials: 'include',
          });
          const body = await response.json().catch(() => null);
          if (response.ok && body) {
            localStorage.setItem('user', JSON.stringify(body));
          }
          return response.ok;
        } catch {
          return false;
        }
      });

      if (currentUser) {
        return;
      }

      await this.page.waitForTimeout(100);
    }

    throw new Error('Login page did not reach an authenticated browser session');
  }
}
