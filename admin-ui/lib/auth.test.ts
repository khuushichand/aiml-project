/* @vitest-environment jsdom */
import { beforeEach, describe, expect, it, vi } from 'vitest';

describe('auth API key storage', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    document.cookie = 'admin_session=; path=/; max-age=0';
    document.cookie = 'admin_auth_mode=; path=/; max-age=0';
    vi.restoreAllMocks();
    vi.resetModules();
  });

  it('stores API key only in memory when setApiKey is called', async () => {
    const auth = await import('./auth');
    auth.setApiKey('test-api-key');

    expect(sessionStorage.getItem('x_api_key')).toBeNull();
    expect(auth.getApiKey()).toBe('test-api-key');
  });

  it('does not persist API key after module reload', async () => {
    const firstLoad = await import('./auth');
    firstLoad.setApiKey('ephemeral-api-key');

    vi.resetModules();
    const secondLoad = await import('./auth');

    expect(secondLoad.getApiKey()).toBeNull();
    expect(secondLoad.hasStoredAuth()).toBe(false);
  });

  it('clears existing API key when password login succeeds', async () => {
    document.cookie = 'admin_session=1; path=/';
    document.cookie = 'admin_auth_mode=jwt; path=/';
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(
        JSON.stringify({ token_type: 'bearer' }),
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

    expect(result).toEqual({
      status: 'authenticated',
    });
    expect(auth.getApiKey()).toBeNull();
    expect(sessionStorage.getItem('x_api_key')).toBeNull();
    expect(auth.getJWTToken()).toBeNull();
    expect(localStorage.getItem('access_token')).toBeNull();
    expect(localStorage.getItem('user')).toContain('"username":"admin"');
  });

  it('clears existing JWT when API key login succeeds', async () => {
    document.cookie = 'admin_session=1; path=/';
    document.cookie = 'admin_auth_mode=single_user; path=/';
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(
        JSON.stringify({
          user: {
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
          },
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      ))
      .mockResolvedValueOnce(new Response(
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
    expect(auth.getApiKey()).toBeNull();
    expect(sessionStorage.getItem('x_api_key')).toBeNull();
    expect(localStorage.getItem('user')).toContain('"username":"ops"');
  });

  it('treats API key login as successful when the validated user is returned before proxy warm-up settles', async () => {
    document.cookie = 'admin_session=1; path=/';
    document.cookie = 'admin_auth_mode=single_user; path=/';
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(
        JSON.stringify({
          user: {
            id: 3,
            uuid: 'user-3',
            username: 'single_user',
            email: '',
            role: 'admin',
            is_active: true,
            is_verified: true,
            storage_quota_mb: 1024,
            storage_used_mb: 12,
            created_at: '2026-02-27T00:00:00Z',
            updated_at: '2026-02-27T00:00:00Z',
          },
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      ))
      .mockResolvedValue(new Response(
        JSON.stringify({ detail: 'Authentication required' }),
        { status: 401, headers: { 'Content-Type': 'application/json' } }
      ));
    vi.stubGlobal('fetch', fetchMock);

    const auth = await import('./auth');

    const ok = await auth.loginWithApiKey('single-user-admin-key');

    expect(ok).toBe(true);
    expect(localStorage.getItem('user')).toContain('"username":"single_user"');
  });

  it('returns MFA challenge details without storing auth when login requires MFA', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(new Response(
      JSON.stringify({
        session_token: 'mfa-session-token',
        mfa_required: true,
        expires_in: 300,
        message: 'MFA required. Submit your TOTP or backup code.',
      }),
      { status: 202, headers: { 'Content-Type': 'application/json' } }
    ));
    vi.stubGlobal('fetch', fetchMock);

    const auth = await import('./auth');
    const result = await auth.loginWithPassword('admin', 'password');

    expect(result).toEqual({
      status: 'mfa_required',
      sessionToken: 'mfa-session-token',
      expiresIn: 300,
      message: 'MFA required. Submit your TOTP or backup code.',
    });
    expect(localStorage.getItem('access_token')).toBeNull();
    expect(localStorage.getItem('user')).toBeNull();
  });

  it('does not treat a stored user profile alone as a durable authenticated session after reload', async () => {
    localStorage.setItem('user', JSON.stringify({ id: 1, username: 'admin' }));

    vi.resetModules();
    const auth = await import('./auth');

    expect(auth.getJWTToken()).toBeNull();
    expect(auth.hasStoredAuth()).toBe(false);
  });

  it('treats the API-key auth mode cookie as single-user mode after reload', async () => {
    document.cookie = 'admin_auth_mode=single_user; path=/';
    document.cookie = 'admin_session=1; path=/';

    vi.resetModules();
    const auth = await import('./auth');

    expect(auth.isSingleUserMode()).toBe(true);
    expect(auth.hasStoredAuth()).toBe(true);
  });
});
