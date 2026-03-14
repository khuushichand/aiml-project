/**
 * Common test helpers for E2E tests
 */
import { type Page } from '@playwright/test';

/**
 * Environment configuration for tests
 */
export const TEST_CONFIG = {
  serverUrl: process.env.TLDW_SERVER_URL || 'http://127.0.0.1:8000',
  apiKey: process.env.TLDW_API_KEY || 'THIS-IS-A-SECURE-KEY-123-FAKE-KEY',
  webUrl: process.env.TLDW_WEB_URL || 'http://localhost:8080',
  allowOffline: process.env.TLDW_E2E_ALLOW_OFFLINE !== '0',
};

/**
 * Seed authentication config in localStorage before page loads
 */
export async function seedAuth(
  page: Page,
  config: Partial<typeof TEST_CONFIG> = {}
): Promise<void> {
  const finalConfig = { ...TEST_CONFIG, ...config };
  await page.addInitScript((cfg) => {
    try {
      localStorage.setItem(
        'tldwConfig',
        JSON.stringify({
          serverUrl: cfg.serverUrl,
          authMode: 'single-user',
          apiKey: cfg.apiKey,
        })
      );
    } catch {}
    try {
      localStorage.setItem('__tldw_first_run_complete', 'true');
    } catch {}
    try {
      if (cfg.allowOffline) {
        localStorage.setItem('__tldw_allow_offline', 'true');
      }
    } catch {}
    // Suppress connection error modals by setting test bypass
    try {
      localStorage.setItem('__tldw_test_bypass', 'true');
    } catch {}
  }, finalConfig);

  // Stub backend endpoints that may return 500 and trigger blocking error modals
  await page.route('**/api/v1/admin/notes/title-settings', route => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ llm_enabled: false, default_strategy: 'heuristic' }),
    });
  });
}

/**
 * Wait for the app connection to be established
 */
export async function waitForConnection(page: Page, timeoutMs = 20000): Promise<void> {
  await page.waitForLoadState('domcontentloaded');

  // Wait for React root to mount
  const root = page.locator('#root, #__next');
  try {
    await root.waitFor({ state: 'attached', timeout: 15000 });
  } catch {
    // Root may take longer, connection check will timeout if app never mounts
  }

  // Wait for connection state
  try {
    await page.waitForFunction(
      () => {
        const store = (window as any).__tldw_useConnectionStore;
        const state = store?.getState?.().state;
        return state?.isConnected === true && state?.phase === 'connected';
      },
      undefined,
      { timeout: timeoutMs }
    );
  } catch {
    // Log connection snapshot for debugging
    await logConnectionState(page, 'connection-timeout');
  }

  // Dismiss any connection error modals that might block interaction
  await dismissConnectionModals(page);

}

/**
 * Dismiss any connection/server error modals (Ant Design modals).
 * Also removes the modal backdrop via DOM manipulation to prevent
 * modals from re-blocking interaction.
 */
export async function dismissConnectionModals(page: Page): Promise<void> {
  // Try clicking Dismiss button first
  try {
    const dismissBtn = page.getByRole('button', { name: /dismiss/i });
    if (await dismissBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await dismissBtn.click();
      await page.waitForTimeout(500);
    }
  } catch {
    // No modal to dismiss
  }

  // Force-remove any remaining modal backdrops via DOM
  await page.evaluate(() => {
    document.querySelectorAll('.ant-modal-root, .ant-modal-wrap, .ant-modal-mask').forEach(el => {
      el.remove();
    });
  }).catch(() => {});
}

/**
 * Log connection state for debugging
 */
export async function logConnectionState(page: Page, label: string): Promise<void> {
  await page.evaluate((tag) => {
    const store = (window as any).__tldw_useConnectionStore;
    if (!store?.getState) {
      console.log('CONNECTION_DEBUG', tag, JSON.stringify({ storeReady: false }));
      return;
    }
    try {
      const state = store.getState().state;
      console.log(
        'CONNECTION_DEBUG',
        tag,
        JSON.stringify({
          phase: state.phase,
          isConnected: state.isConnected,
          isChecking: state.isChecking,
          errorKind: state.errorKind,
        })
      );
    } catch {}
  }, label);
}

/**
 * Make authenticated API request
 */
export async function fetchWithApiKey(
  url: string,
  apiKey: string = TEST_CONFIG.apiKey,
  init: RequestInit = {}
): Promise<Response> {
  const headers = {
    'x-api-key': apiKey,
    ...(init.headers || {}),
  };
  return fetch(url, { ...init, headers });
}

/**
 * Wait for network to be idle
 */
export async function waitForNetworkIdle(page: Page, timeoutMs = 30000): Promise<void> {
  try {
    await page.waitForLoadState('networkidle', { timeout: timeoutMs });
  } catch {
    // Non-blocking - some pages may have long-polling
  }
}

/**
 * Normalize URL by removing trailing slash
 */
export function normalizeUrl(url: string): string {
  return url.replace(/\/$/, '');
}

/**
 * Wait for element with retry logic
 */
export async function waitForElement(
  page: Page,
  selector: string,
  options: { timeout?: number; state?: 'attached' | 'visible' | 'hidden' } = {}
): Promise<void> {
  const { timeout = 10000, state = 'visible' } = options;
  const element = page.locator(selector);
  await element.waitFor({ state, timeout });
}

/**
 * Dismiss any visible modals or dialogs
 */
export async function dismissModals(page: Page): Promise<void> {
  // Dismiss Ant Design modals
  const modalCloseButtons = page.locator('.ant-modal-close');
  const count = await modalCloseButtons.count();
  for (let i = 0; i < count; i++) {
    const button = modalCloseButtons.nth(i);
    if (await button.isVisible()) {
      await button.click();
    }
  }
}

/**
 * Take a screenshot with a descriptive name
 */
export async function takeDebugScreenshot(page: Page, name: string): Promise<void> {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  await page.screenshot({
    path: `test-results/debug-${name}-${timestamp}.png`,
    fullPage: true,
  });
}

/**
 * Clear test data created during tests
 */
export async function cleanupTestData(
  page: Page,
  options: { conversations?: boolean; media?: boolean } = {}
): Promise<void> {
  // Clear localStorage items created by tests
  await page.evaluate((opts) => {
    if (opts.conversations) {
      // Clear conversation-related storage
      const keys = Object.keys(localStorage).filter(
        (k) => k.startsWith('conv_') || k.startsWith('chat_')
      );
      keys.forEach((k) => localStorage.removeItem(k));
    }
    if (opts.media) {
      // Clear media-related storage
      const keys = Object.keys(localStorage).filter(
        (k) => k.startsWith('media_') || k.startsWith('ingest_')
      );
      keys.forEach((k) => localStorage.removeItem(k));
    }
  }, options);
}

/**
 * Generate unique test identifiers
 */
export function generateTestId(prefix = 'test'): string {
  const timestamp = Date.now();
  const random = Math.random().toString(36).substring(2, 8);
  return `${prefix}-${timestamp}-${random}`;
}

/**
 * Patterns for console/error messages that are benign and should be ignored
 */
export const BENIGN_PATTERNS = [
  /ResizeObserver loop/,
  /Non-Error promise rejection/,
  /net::ERR_ABORTED/,
  /chrome-extension/,
  /Download the React DevTools/,
  /Fast Refresh/,
  /\[HMR\]/,
  /favicon\.ico.*404/,
  /Failed to load source map/,
  /Warning.*findDOMNode is deprecated/,
  /Hydration failed/,
  /There was an error while hydrating/,
  /cannot connect to an AudioNode belonging to a different audio context/i,
];

/**
 * Check if an error/warning message is benign
 */
export function isBenign(text: string): boolean {
  return BENIGN_PATTERNS.some((p) => p.test(text));
}

/**
 * Retry an action with exponential backoff
 */
export async function retry<T>(
  action: () => Promise<T>,
  options: { maxAttempts?: number; delayMs?: number } = {}
): Promise<T> {
  const { maxAttempts = 3, delayMs = 500 } = options;
  let lastError: Error | undefined;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await action();
    } catch (error) {
      lastError = error as Error;
      if (attempt < maxAttempts) {
        await new Promise((resolve) => setTimeout(resolve, delayMs * Math.pow(2, attempt - 1)));
      }
    }
  }

  throw lastError;
}
