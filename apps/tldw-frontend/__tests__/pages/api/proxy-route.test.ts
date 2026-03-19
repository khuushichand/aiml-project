import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  createApiRequest,
  createApiResponse,
} from './test-utils';

describe('hosted proxy api route', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.restoreAllMocks();
    vi.clearAllMocks();
    process.env.NEXT_PUBLIC_API_URL = 'http://127.0.0.1:8000';
    process.env.NEXT_PUBLIC_API_VERSION = 'v1';
  });

  it('forwards requests through the same-origin proxy without trusting browser bearer headers', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: {
          'Content-Type': 'application/json',
          ETag: '"proxy-etag"',
        },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const handler = (await import('@web/pages/api/proxy/[...path]')).default;
    const req = createApiRequest({
      method: 'GET',
      url: '/api/proxy/users/me?view=full',
      query: {
        path: ['users', 'me'],
        view: 'full',
      },
      headers: {
        accept: 'application/json',
        authorization: 'Bearer browser-token',
        cookie: 'tldw_access_token=proxy-access',
      },
    });
    const res = createApiResponse();

    await handler(req, res);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [forwardedUrl, forwardedInit] = fetchMock.mock.calls[0];
    expect(forwardedUrl).toBe('http://127.0.0.1:8000/api/v1/users/me?view=full');
    expect(forwardedInit.method).toBe('GET');
    expect((forwardedInit.headers as Headers).get('Authorization')).toBe('Bearer proxy-access');
    expect((forwardedInit.headers as Headers).get('accept')).toBe('application/json');
    expect((forwardedInit.headers as Headers).get('Authorization')).not.toBe('Bearer browser-token');

    expect(res.statusCode).toBe(200);
    expect(res.body).toEqual({ ok: true });
    expect(res.getHeader('etag')).toBe('"proxy-etag"');
  });
});
