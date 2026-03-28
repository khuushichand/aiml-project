/* @vitest-environment node */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { NextRequest } from 'next/server';

const buildApiUrlForRequest = vi.fn((_req: unknown, path: string) => `https://example.test${path}`);
const getBackendAuthHeaders = vi.fn(() => new Headers({ Authorization: 'Bearer test-token' }));
const clearAdminSessionCookies = vi.fn();
const invalidateAuthCache = vi.fn().mockResolvedValue(undefined);

vi.mock('@/lib/api-config', () => ({
  buildApiUrlForRequest,
}));

vi.mock('@/lib/server-auth', () => ({
  clearAdminSessionCookies,
  getBackendAuthHeaders,
  ACCESS_TOKEN_COOKIE: 'access_token',
  API_KEY_COOKIE: 'x_api_key',
  LEGACY_API_KEY_COOKIE: 'x-api-key',
}));

vi.mock('@/middleware', () => ({
  invalidateAuthCache,
}));

describe('POST /api/auth/logout', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
  });

  it('logs backend logout failures and still clears local session cookies', async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error('backend unavailable'));
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    vi.stubGlobal('fetch', fetchMock);

    const { POST } = await import('./route');
    const request = new NextRequest('http://localhost/api/auth/logout', { method: 'POST' });
    const response = await POST(request);

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ ok: true });
    expect(getBackendAuthHeaders).toHaveBeenCalledWith(request);
    expect(fetchMock).toHaveBeenCalledWith('https://example.test/auth/logout', {
      method: 'POST',
      headers: new Headers({ Authorization: 'Bearer test-token' }),
      cache: 'no-store',
    });
    expect(warnSpy).toHaveBeenCalledTimes(1);
    const warnArg = warnSpy.mock.calls[0][0] as string;
    expect(warnArg).toContain('Backend logout failed');
    expect(warnArg).toContain('backend unavailable');
    expect(warnArg).toContain('auth/logout');
    expect(clearAdminSessionCookies).toHaveBeenCalledTimes(1);
    expect(clearAdminSessionCookies).toHaveBeenCalledWith(expect.objectContaining({
      cookies: expect.anything(),
    }));
  });
});
