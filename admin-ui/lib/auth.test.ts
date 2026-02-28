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

  it('clears existing API key when password login succeeds', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(
        JSON.stringify({ access_token: 'jwt-token', token_type: 'bearer' }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      ))
      .mockResolvedValueOnce(new Response(
        JSON.stringify({
          id: 1,
          uuid: 'user-1',
          username: 'admin',
          email: 'admin@example.com',
          role: 'admin',
          is_active: true,
          is_verified: true,
          storage_quota_mb: 1024,
          storage_used_mb: 64,
          created_at: '2026-02-27T00:00:00Z',
          updated_at: '2026-02-27T00:00:00Z',
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      ));
    vi.stubGlobal('fetch', fetchMock);

    const auth = await import('./auth');
    auth.setApiKey('legacy-api-key');
    const result = await auth.loginWithPassword('admin', 'password');

    expect(result?.access_token).toBe('jwt-token');
    expect(auth.getApiKey()).toBeNull();
    expect(sessionStorage.getItem('x_api_key')).toBeNull();
    expect(localStorage.getItem('access_token')).toBe('jwt-token');
  });

  it('clears existing JWT when API key login succeeds', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({
        id: 2,
        uuid: 'user-2',
        username: 'ops',
        email: 'ops@example.com',
        role: 'admin',
        is_active: true,
        is_verified: true,
        storage_quota_mb: 1024,
        storage_used_mb: 10,
        created_at: '2026-02-27T00:00:00Z',
        updated_at: '2026-02-27T00:00:00Z',
      }),
      { status: 200, headers: { 'Content-Type': 'application/json' } }
    ));
    vi.stubGlobal('fetch', fetchMock);

    const auth = await import('./auth');
    localStorage.setItem('access_token', 'legacy-jwt-token');

    const ok = await auth.loginWithApiKey('fresh-api-key');

    expect(ok).toBe(true);
    expect(auth.getJWTToken()).toBeNull();
    expect(localStorage.getItem('access_token')).toBeNull();
    expect(sessionStorage.getItem('x_api_key')).toBe('fresh-api-key');
  });
});
