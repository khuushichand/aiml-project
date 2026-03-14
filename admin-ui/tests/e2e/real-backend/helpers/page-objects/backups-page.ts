import { expect, type Locator, type Page } from '@playwright/test';

type BackupScheduleInput = {
  dataset: 'media' | 'chacha' | 'prompts' | 'evaluations' | 'audit' | 'authnz';
  targetUserId?: number;
  frequency: 'daily' | 'weekly' | 'monthly';
  timeOfDay: string;
  retentionCount: number;
};

export class BackupsPage {
  readonly page: Page;
  readonly scheduleTabButton: Locator;
  readonly backupsHeading: Locator;
  readonly scheduleDatasetSelect: Locator;
  readonly scheduleFrequencySelect: Locator;
  readonly scheduleTimeInput: Locator;
  readonly scheduleRetentionInput: Locator;
  readonly createScheduleButton: Locator;

  constructor(page: Page) {
    this.page = page;
    this.scheduleTabButton = page.getByRole('button', { name: 'Schedule' });
    this.backupsHeading = page.getByRole('heading', { name: /^backups$/i });
    this.scheduleDatasetSelect = page.getByLabel('Dataset');
    this.scheduleFrequencySelect = page.getByLabel('Frequency');
    this.scheduleTimeInput = page.getByLabel('Time of day');
    this.scheduleRetentionInput = page.getByLabel('Retention count');
    this.createScheduleButton = page.getByRole('button', { name: 'Create schedule' });
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
      const backupsHeadingVisible = await this.backupsHeading.isVisible().catch(() => false);
      if (backupsHeadingVisible) {
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
    throw new Error('Backups page did not become ready or redirect to login');
  }

  async gotoScheduleTab(): Promise<void> {
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
        await expect(this.backupsHeading).toBeVisible();
        await this.scheduleTabButton.click();
        await expect(this.page.getByText(/backup schedules are shared platform policy/i)).toBeVisible();
        await expect(this.scheduleDatasetSelect).toBeVisible();
        return;
      } catch (error) {
        lastError = error;
        await this.page.waitForTimeout(1_000);
      }
    }
    throw lastError instanceof Error ? lastError : new Error('Failed to open backup schedule tab');
  }

  async reloadScheduleTab(): Promise<void> {
    await this.page.reload({ waitUntil: 'domcontentloaded' });
    await this.gotoScheduleTab();
  }

  private scheduleRow(filterText: string): Locator {
    return this.page
      .locator('[data-testid^="backup-schedule-row-"]')
      .filter({ hasText: filterText })
      .first();
  }

  async createSchedule(input: BackupScheduleInput): Promise<string> {
    await this.scheduleDatasetSelect.selectOption(input.dataset);
    if (input.targetUserId !== undefined) {
      await this.page.getByLabel('Target user').selectOption(String(input.targetUserId));
    }
    await this.scheduleFrequencySelect.selectOption(input.frequency);
    await this.scheduleTimeInput.fill(input.timeOfDay);
    await this.scheduleRetentionInput.fill(String(input.retentionCount));
    await this.createScheduleButton.click();

    const row = this.scheduleRow(input.dataset);
    await expect(row).toBeVisible();
    const testId = await row.getAttribute('data-testid');
    if (!testId) {
      throw new Error(`Missing backup schedule row test id for dataset ${input.dataset}`);
    }
    return testId.replace('backup-schedule-row-', '');
  }

  async expectScheduleRow(dataset: string, targetText: string, scheduleText: string): Promise<void> {
    const row = this.scheduleRow(dataset).filter({ hasText: targetText }).filter({ hasText: scheduleText });
    await expect(row).toBeVisible();
  }

  async expectNoScheduleRow(dataset: string): Promise<void> {
    await expect(this.page.locator('[data-testid^="backup-schedule-row-"]').filter({ hasText: dataset })).toHaveCount(0);
  }

  async expectScheduleRunMetadata(scheduleId: string): Promise<void> {
    const row = this.page.getByTestId(`backup-schedule-row-${scheduleId}`);
    await expect(row).toBeVisible();
    await expect(row).toContainText(/succeeded/i);
    await expect(row.locator('td').nth(4)).not.toHaveText('—');
  }
}
