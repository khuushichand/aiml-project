import { expect, type Locator, type Page } from '@playwright/test';

type AlertRuleInput = {
  metric?: 'cpu' | 'memory' | 'diskUsage' | 'throughput' | 'activeConnections' | 'queueDepth';
  operator?: '>' | '<' | '==';
  threshold: string;
  durationMinutes?: '1' | '5' | '10' | '15' | '30' | '60' | '240' | '1440';
  severity?: 'warning' | 'critical' | 'error' | 'info';
};

export class MonitoringPage {
  readonly page: Page;
  readonly metricSelect: Locator;
  readonly operatorSelect: Locator;
  readonly thresholdInput: Locator;
  readonly durationSelect: Locator;
  readonly severitySelect: Locator;
  readonly addRuleButton: Locator;
  readonly historyPanel: Locator;

  constructor(page: Page) {
    this.page = page;
    this.metricSelect = page.locator('#alert-rule-metric');
    this.operatorSelect = page.locator('#alert-rule-operator');
    this.thresholdInput = page.locator('#alert-rule-threshold');
    this.durationSelect = page.locator('#alert-rule-duration');
    this.severitySelect = page.locator('#alert-rule-severity');
    this.addRuleButton = page.getByRole('button', { name: 'Add Rule' });
    this.historyPanel = page.getByTestId('alert-history-panel');
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

  private async waitForEntryState(): Promise<'ready' | 'denied' | 'login'> {
    const deadline = Date.now() + 15_000;
    let loginVisibleSince: number | null = null;
    while (Date.now() < deadline) {
      const rulesHeadingVisible = await this.page
        .getByRole('heading', { name: /alert rules/i })
        .isVisible()
        .catch(() => false);
      if (rulesHeadingVisible) {
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
    throw new Error('Monitoring page did not become ready, denied, or redirect to login');
  }

  async goto(): Promise<void> {
    let lastError: unknown;
    for (let attempt = 0; attempt < 5; attempt += 1) {
      try {
        try {
          await this.page.goto('/monitoring', { waitUntil: 'domcontentloaded' });
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
    throw lastError instanceof Error ? lastError : new Error('Failed to open /monitoring');
  }

  async expectReady(): Promise<void> {
    await expect(this.page.getByRole('heading', { name: /alert rules/i })).toBeVisible();
    await expect(this.page.getByRole('heading', { name: /^alerts$/i })).toBeVisible();
  }

  async expectDenied(): Promise<void> {
    await expect(this.page.getByText('You do not have permission to access this page.')).toBeVisible();
  }

  async reload(): Promise<void> {
    await this.page.reload({ waitUntil: 'domcontentloaded' });
    await this.expectReady();
  }

  async createRule(input: AlertRuleInput): Promise<void> {
    await this.metricSelect.selectOption(input.metric ?? 'cpu');
    await this.operatorSelect.selectOption(input.operator ?? '>');
    await this.thresholdInput.fill(input.threshold);
    await this.durationSelect.selectOption(input.durationMinutes ?? '15');
    await this.severitySelect.selectOption(input.severity ?? 'critical');
    await this.addRuleButton.click();
  }

  async expectRulePresent(threshold: string): Promise<void> {
    await expect(this.page.getByText(threshold, { exact: true }).first()).toBeVisible();
  }

  async assignAlert(alertId: string, userId: string): Promise<void> {
    await this.page.getByTestId(`alert-assignee-select-${alertId}`).selectOption(userId);
  }

  async expectAlertAssigned(alertId: string, userId: string): Promise<void> {
    await expect(this.page.getByTestId(`alert-assignee-select-${alertId}`)).toHaveValue(userId);
  }

  async openHistory(): Promise<void> {
    const expanded = await this.historyPanel.evaluate((element) => element.hasAttribute('open'));
    if (!expanded) {
      await this.historyPanel.locator('summary').click();
    }
    await expect(this.page.getByTestId('alert-history-timeline')).toBeVisible();
  }

  async expectHistoryContains(text: string): Promise<void> {
    await this.openHistory();
    await expect(this.page.getByTestId('alert-history-timeline')).toContainText(text);
  }
}
