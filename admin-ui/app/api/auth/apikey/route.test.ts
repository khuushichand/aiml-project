/* @vitest-environment node */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { NextRequest } from 'next/server';

const setApiKeySessionCookies = vi.fn();
const buildApiUrl = vi.fn((path: string) => `https://example.test${path}`);

vi.mock('@/lib/api-config', () => ({
  buildApiUrl,
}));

vi.mock('@/lib/server-auth', () => ({
  setApiKeySessionCookies,
}));

describe('POST /api/auth/apikey', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
    process.env.AUTH_MODE = 'single_user';
    process.env.ADMIN_UI_ALLOW_API_KEY_LOGIN = 'true';
    process.env.NEXT_PUBLIC_ALLOW_ADMIN_API_KEY_LOGIN = 'false';
    delete process.env.ADMIN_UI_ENTERPRISE_MODE;
  });

  it('rejects API-key login when enterprise mode is enabled', async () => {
    process.env.ADMIN_UI_ENTERPRISE_MODE = 'true';
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    const { POST } = await import('./route');
    const response = await POST(new NextRequest('http://localhost/api/auth/apikey', {
      method: 'POST',
      body: JSON.stringify({ apiKey: 'admin-key' }),
      headers: {
        'Content-Type': 'application/json',
      },
    }));

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toEqual({
      detail: 'Admin UI API key login is disabled. Use multi-user credentials.',
    });
    expect(fetchMock).not.toHaveBeenCalled();
    expect(setApiKeySessionCookies).not.toHaveBeenCalled();
  });

  it('rejects API-key login when the admin UI is not running in single-user auth mode', async () => {
    process.env.AUTH_MODE = 'multi_user';
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    const { POST } = await import('./route');
    const response = await POST(new NextRequest('http://localhost/api/auth/apikey', {
      method: 'POST',
      body: JSON.stringify({ apiKey: 'admin-key' }),
      headers: {
        'Content-Type': 'application/json',
      },
    }));

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toEqual({
      detail: 'Admin UI API key login is disabled. Use multi-user credentials.',
    });
    expect(fetchMock).not.toHaveBeenCalled();
    expect(setApiKeySessionCookies).not.toHaveBeenCalled();
  });

  it('rejects API-key login when only the public UI flag is enabled', async () => {
    process.env.ADMIN_UI_ALLOW_API_KEY_LOGIN = 'false';
    process.env.NEXT_PUBLIC_ALLOW_ADMIN_API_KEY_LOGIN = 'true';
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    const { POST } = await import('./route');
    const response = await POST(new NextRequest('http://localhost/api/auth/apikey', {
      method: 'POST',
      body: JSON.stringify({ apiKey: 'admin-key' }),
      headers: {
        'Content-Type': 'application/json',
      },
    }));

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toEqual({
      detail: 'Admin UI API key login is disabled. Use multi-user credentials.',
    });
    expect(fetchMock).not.toHaveBeenCalled();
    expect(setApiKeySessionCookies).not.toHaveBeenCalled();
  });
});
