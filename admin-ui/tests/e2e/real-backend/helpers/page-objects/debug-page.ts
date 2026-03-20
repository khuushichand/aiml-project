import { expect, type Page } from '@playwright/test';

export class DebugPage {
  constructor(readonly page: Page) {}

  private async primeAuthenticatedUser(): Promise<boolean> {
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
        return true;
      }
      await this.page.waitForTimeout(100);
    }
    return false;
  }

  private async isLoginScreen(): Promise<boolean> {
    return this.page.url().includes('/login');
  }

  private async waitForEntryState(): Promise<'ready' | 'denied' | 'login'> {
    const deadline = Date.now() + 15_000;
    let loginVisibleSince: number | null = null;
    while (Date.now() < deadline) {
      const debugHeadingVisible = await this.page
        .getByRole('heading', { name: /debug tools/i })
        .isVisible()
        .catch(() => false);
      if (debugHeadingVisible) {
        return 'ready';
      }

      const deniedVisible = await this.page
        .getByText('You do not have permission to access this page.')
        .isVisible()
        .catch(() => false);
      if (deniedVisible) {
        return 'denied';
      }

      const onLoginUrl = await this.isLoginScreen();
      const loginHeadingVisible = onLoginUrl
        ? await this.page.getByRole('heading', { name: /tldw admin/i }).isVisible().catch(() => false)
        : false;
      if (onLoginUrl && loginHeadingVisible) {
        if (loginVisibleSince === null) {
          loginVisibleSince = Date.now();
        } else if (Date.now() - loginVisibleSince >= 750) {
          return 'login';
        }
      } else {
        loginVisibleSince = null;
      }
      await this.page.waitForTimeout(100);
    }
    throw new Error('Debug page did not become ready, denied, or redirect to login');
  }

  async goto(): Promise<void> {
    let lastError: unknown;
    for (let attempt = 0; attempt < 5; attempt += 1) {
      try {
        try {
          await this.page.goto('/debug', { waitUntil: 'domcontentloaded' });
        } catch (error) {
          if (!(error instanceof Error) || !error.message.includes('net::ERR_ABORTED')) {
            throw error;
          }
        }
        const entryState = await this.waitForEntryState();
        if (entryState === 'login') {
          await this.primeAuthenticatedUser();
          await this.page.waitForTimeout(750);
          continue;
        }
        return;
      } catch (error) {
        lastError = error;
        await this.page.waitForTimeout(1_000);
      }
    }
    throw lastError instanceof Error ? lastError : new Error('Failed to open /debug');
  }

  async expectAllowed(): Promise<void> {
    await expect(this.page.getByRole('heading', { name: /debug tools/i })).toBeVisible();
  }

  async expectDenied(): Promise<void> {
    await expect(this.page.getByText('You do not have permission to access this page.')).toBeVisible();
  }
}
