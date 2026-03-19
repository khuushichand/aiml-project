import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  createApiRequest,
  createApiResponse,
} from './test-utils';

describe('hosted auth api routes', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.restoreAllMocks();
    vi.clearAllMocks();
    process.env.NEXT_PUBLIC_API_URL = 'http://127.0.0.1:8000';
    process.env.NEXT_PUBLIC_API_VERSION = 'v1';
    delete process.env.NODE_ENV;
  });

  it('login stores hosted session cookies and strips tokens from the JSON response', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          access_token: 'access-1',
          refresh_token: 'refresh-1',
          token_type: 'bearer',
          expires_in: 1800,
          session_token: 'mfa-session',
        }),
        {
          status: 200,
          headers: {
            'Content-Type': 'application/json',
          },
        },
      ),
    );
    vi.stubGlobal('fetch', fetchMock);

    const handler = (await import('@web/pages/api/auth/login')).default;
    const req = createApiRequest({
      method: 'POST',
      url: '/api/auth/login',
      headers: {
        'content-type': 'application/x-www-form-urlencoded',
      },
      body: 'username=alice&password=Secret123!',
    });
    const res = createApiResponse();

    await handler(req, res);

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/v1/auth/login',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: 'username=alice&password=Secret123!',
      },
    );
    expect(res.statusCode).toBe(200);
    expect(res.body).toEqual({
      token_type: 'bearer',
      expires_in: 1800,
      session_token: 'mfa-session',
    });

    const setCookie = res.getHeader('set-cookie');
    expect(Array.isArray(setCookie)).toBe(true);
    expect((setCookie as string[]).some((cookie) => cookie.includes('tldw_access_token=access-1'))).toBe(true);
    expect((setCookie as string[]).some((cookie) => cookie.includes('tldw_refresh_token=refresh-1'))).toBe(true);
    expect((setCookie as string[]).every((cookie) => cookie.includes('Path=/'))).toBe(true);
  });

  it('logout clears hosted session cookies even when backend logout fails', async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error('backend unavailable'));
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    vi.stubGlobal('fetch', fetchMock);

    const handler = (await import('@web/pages/api/auth/logout')).default;
    const req = createApiRequest({
      method: 'POST',
      url: '/api/auth/logout',
      headers: {
        cookie: 'tldw_access_token=logout-access; tldw_refresh_token=logout-refresh',
      },
    });
    const res = createApiResponse();

    await handler(req, res);

    expect(res.statusCode).toBe(200);
    expect(res.body).toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, logoutInit] = fetchMock.mock.calls[0];
    expect(logoutInit).toEqual(
      expect.objectContaining({
        method: 'POST',
      }),
    );
    expect(logoutInit.headers).toEqual(
      expect.objectContaining({
        authorization: 'Bearer logout-access',
      }),
    );
    expect(warnSpy).toHaveBeenCalledWith('Hosted frontend backend logout failed', {
      error: 'backend unavailable',
    });

    const setCookie = res.getHeader('set-cookie') as string[];
    expect(setCookie.every((cookie) => cookie.includes('Max-Age=0'))).toBe(true);
  });

  it('session returns the current user when hosted cookies are present', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ id: 7, username: 'alice', email: 'alice@example.com' }),
        {
          status: 200,
          headers: {
            'Content-Type': 'application/json',
          },
        },
      ),
    );
    vi.stubGlobal('fetch', fetchMock);

    const handler = (await import('@web/pages/api/auth/session')).default;
    const req = createApiRequest({
      method: 'GET',
      url: '/api/auth/session',
      headers: {
        cookie: 'tldw_access_token=session-access',
      },
    });
    const res = createApiResponse();

    await handler(req, res);

    expect(res.statusCode).toBe(200);
    expect(res.body).toEqual({
      authenticated: true,
      authMode: 'jwt',
      user: {
        id: 7,
        username: 'alice',
        email: 'alice@example.com',
      },
    });
  });

  it('verify-email translates the hosted request into the backend query-string contract', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ message: 'Email verified successfully' }), {
        status: 200,
        headers: {
          'Content-Type': 'application/json',
        },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const handler = (await import('@web/pages/api/auth/verify-email')).default;
    const req = createApiRequest({
      method: 'POST',
      url: '/api/auth/verify-email',
      headers: {
        'content-type': 'application/json',
      },
      body: {
        token: 'verify-token-1',
      },
    });
    const res = createApiResponse();

    await handler(req, res);

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/v1/auth/verify-email?token=verify-token-1',
      {
        method: 'GET',
        headers: {},
      },
    );
    expect(res.statusCode).toBe(200);
    expect(res.body).toEqual({ message: 'Email verified successfully' });
  });

  it('magic-link verification sets hosted session cookies and strips token fields', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          access_token: 'magic-access',
          refresh_token: 'magic-refresh',
          token_type: 'bearer',
          expires_in: 1800,
        }),
        {
          status: 200,
          headers: {
            'Content-Type': 'application/json',
          },
        },
      ),
    );
    vi.stubGlobal('fetch', fetchMock);

    const handler = (await import('@web/pages/api/auth/magic-link/verify')).default;
    const req = createApiRequest({
      method: 'POST',
      url: '/api/auth/magic-link/verify',
      headers: {
        'content-type': 'application/json',
      },
      body: {
        token: 'magic-token-1',
      },
    });
    const res = createApiResponse();

    await handler(req, res);

    expect(res.statusCode).toBe(200);
    expect(res.body).toEqual({
      token_type: 'bearer',
      expires_in: 1800,
    });
    const setCookie = res.getHeader('set-cookie') as string[];
    expect(setCookie.some((cookie) => cookie.includes('tldw_access_token=magic-access'))).toBe(true);
    expect(setCookie.some((cookie) => cookie.includes('tldw_refresh_token=magic-refresh'))).toBe(true);
  });
});
