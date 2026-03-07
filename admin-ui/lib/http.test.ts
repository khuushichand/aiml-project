/* @vitest-environment jsdom */
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('./auth', () => ({
  getApiKey: vi.fn(() => null),
  getJWTToken: vi.fn(() => null),
  logout: vi.fn(() => Promise.resolve()),
}));

describe('http auth transport', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ ok: true }),
      { status: 200, headers: { 'Content-Type': 'application/json' } }
    )));
  });

  it('routes JSON requests through the same-origin proxy without browser bearer headers', async () => {
    const { requestJson } = await import('./http');

    await requestJson('/users/me');

    expect(fetch).toHaveBeenCalledWith('/api/proxy/users/me', expect.objectContaining({
      credentials: 'include',
      headers: expect.any(Headers),
    }));

    const [, init] = vi.mocked(fetch).mock.calls[0] ?? [];
    const headers = new Headers(init?.headers);
    expect(headers.get('Authorization')).toBeNull();
    expect(headers.get('X-API-KEY')).toBeNull();
  });

  it('forwards in-memory API keys only to the same-origin proxy', async () => {
    const auth = await import('./auth');
    vi.mocked(auth.getApiKey).mockReturnValue('ephemeral-api-key');

    const { requestJson } = await import('./http');
    await requestJson('/users/me');

    const [, init] = vi.mocked(fetch).mock.calls[0] ?? [];
    const headers = new Headers(init?.headers);
    expect(headers.get('X-API-KEY')).toBe('ephemeral-api-key');
  });
});
