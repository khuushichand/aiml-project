import { expect, type Locator, type Page } from '@playwright/test';

export class DataSubjectRequestsPage {
  readonly page: Page;
  readonly requesterInput: Locator;
  readonly requestTypeSelect: Locator;
  readonly submitButton: Locator;
  readonly requestLog: Locator;

  constructor(page: Page) {
    this.page = page;
    this.requesterInput = page.getByLabel('User identifier (email or user ID)');
    this.requestTypeSelect = page.getByLabel('Request type');
    this.submitButton = page.getByRole('button', { name: 'Submit request' });
    this.requestLog = page.getByTestId('dsr-request-log');
  }

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

  private async waitForEntryState(): Promise<'ready' | 'login'> {
    const deadline = Date.now() + 15_000;
    let loginVisibleSince: number | null = null;
    while (Date.now() < deadline) {
      const dataOpsHeadingVisible = await this.page
        .getByRole('heading', { name: /data ops/i })
        .isVisible()
        .catch(() => false);
      if (dataOpsHeadingVisible) {
        return 'ready';
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
    throw new Error('Data Ops page did not become ready or redirect to login');
  }

  async expectReady(): Promise<void> {
    await expect(this.page.getByRole('heading', { name: /data ops/i })).toBeVisible();
    await expect(this.page.getByRole('heading', { name: /data subject requests/i })).toBeVisible();
    await expect(this.requestLog).toBeVisible();
  }

  async goto(): Promise<void> {
    let lastError: unknown;
    for (let attempt = 0; attempt < 5; attempt += 1) {
      try {
        try {
          await this.page.goto('/data-ops', { waitUntil: 'domcontentloaded' });
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
        await this.expectReady();
        return;
      } catch (error) {
        lastError = error;
        await this.page.waitForTimeout(1_000);
      }
    }
    throw lastError instanceof Error ? lastError : new Error('Failed to open /data-ops');
  }

  async reload(): Promise<void> {
    await this.page.reload();
    await expect(this.page.getByRole('heading', { name: /data subject requests/i })).toBeVisible();
    await expect(this.requestLog).toBeVisible();
  }

  async submitAccessRequest(requesterIdentifier: string): Promise<void> {
    await this.requesterInput.fill(requesterIdentifier);
    await this.requestTypeSelect.selectOption('access');
    await this.submitButton.click();
  }

  async expectAccessSummary(): Promise<void> {
    await expect(this.page.getByTestId('dsr-access-summary')).toBeVisible();
  }

  async expectRecordedRow(requesterIdentifier: string, status: string): Promise<void> {
    const row = this.requestLog
      .getByTestId('dsr-request-log-row')
      .filter({ hasText: requesterIdentifier })
      .filter({ hasText: status })
      .first();
    await expect(row).toBeVisible();
  }

  async expectNoRecordedRow(requesterIdentifier: string): Promise<void> {
    await expect(this.requestLog.getByText(requesterIdentifier)).toHaveCount(0);
  }

  async expectRequestFailure(messagePattern: RegExp): Promise<void> {
    const failureToast = this.page.getByRole('alert').filter({ hasText: 'Request failed' }).last();
    await expect(failureToast).toBeVisible();
    await expect(failureToast).toContainText(messagePattern);
  }
}
