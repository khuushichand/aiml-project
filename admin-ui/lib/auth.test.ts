/* @vitest-environment jsdom */
import { beforeEach, describe, expect, it, vi } from 'vitest';

describe('auth API key storage', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.restoreAllMocks();
    vi.resetModules();
  });

  it('persists API key in sessionStorage when setApiKey is called', async () => {
    const auth = await import('./auth');
    auth.setApiKey('test-api-key');

    expect(sessionStorage.getItem('x_api_key')).toBe('test-api-key');
    expect(auth.getApiKey()).toBe('test-api-key');
  });

  it('loads API key from sessionStorage after module reload', async () => {
    const firstLoad = await import('./auth');
    firstLoad.setApiKey('persisted-api-key');

    vi.resetModules();
    const secondLoad = await import('./auth');

    expect(secondLoad.getApiKey()).toBe('persisted-api-key');
    expect(secondLoad.hasStoredAuth()).toBe(true);
  });
});
