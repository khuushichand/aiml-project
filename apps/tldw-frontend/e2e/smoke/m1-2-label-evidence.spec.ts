import type { Page } from '@playwright/test';
import { test, expect, seedAuth } from './smoke.setup';

const EVIDENCE_DIR = '../../Docs/Product/WebUI/evidence/m1_2_label_alignment_2026_02_13';

async function captureDesktopPage(page: Page, slug: string, route: string): Promise<void> {
  await page.goto(route, { waitUntil: 'domcontentloaded', timeout: 30_000 });
  await page.waitForLoadState('networkidle', { timeout: 30_000 }).catch(() => {});
  await page.waitForTimeout(750);
  await page.screenshot({
    path: `${EVIDENCE_DIR}/desktop-${slug}.png`,
    fullPage: true,
  });
}

async function captureMobilePage(page: Page, slug: string, route: string): Promise<void> {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto(route, { waitUntil: 'domcontentloaded', timeout: 30_000 });
  await page.waitForLoadState('networkidle', { timeout: 30_000 }).catch(() => {});
  await page.waitForTimeout(750);
  await page.screenshot({
    path: `${EVIDENCE_DIR}/mobile-${slug}.png`,
    fullPage: true,
  });
}

test.describe('M1.2 Label Alignment Evidence', () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page);
  });

  test('capture desktop evidence set', async ({ page }) => {
    await captureDesktopPage(page, 'chat', '/chat');
    await expect(page.getByTestId('chat-input')).toBeVisible({ timeout: 15_000 });

    await captureDesktopPage(page, 'prompts', '/prompts');
    await expect(page.getByText('Prompts').first()).toBeVisible({ timeout: 10_000 });

    await captureDesktopPage(page, 'settings-tldw', '/settings/tldw');
    await expect(page.getByText('tldw Server Configuration')).toBeVisible({ timeout: 15_000 });
  });

  test('capture mobile evidence set', async ({ page }) => {
    await captureMobilePage(page, 'chat', '/chat');
    await captureMobilePage(page, 'prompts', '/prompts');
    await captureMobilePage(page, 'settings-tldw', '/settings/tldw');
  });
});
