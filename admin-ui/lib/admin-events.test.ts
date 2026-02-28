/* @vitest-environment jsdom */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const makeEventStreamResponse = (frames: string[]): Response => {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const frame of frames) {
        controller.enqueue(encoder.encode(frame));
      }
      controller.close();
    },
  });

  return new Response(stream, {
    status: 200,
    headers: {
      'Content-Type': 'text/event-stream',
    },
  });
};

describe('subscribeToAdminEvents', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.restoreAllMocks();
    vi.resetModules();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('does not include credentials in query params and sends auth as headers', async () => {
    localStorage.setItem('access_token', 'jwt-token-value');

    const fetchMock = vi.fn().mockResolvedValue(
      makeEventStreamResponse([
        'event: connected\ndata: {"event":"connected","category":"system","data":{},"timestamp":"2026-02-27T00:00:00Z"}\n\n',
      ])
    );
    vi.stubGlobal('fetch', fetchMock);

    const handler = vi.fn();
    const onConnect = vi.fn();
    const { subscribeToAdminEvents } = await import('./admin-events');

    const unsubscribe = subscribeToAdminEvents(handler, {
      categories: ['system', 'security'],
      onConnect,
    });

    await vi.waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain('/admin/events/stream?categories=system%2Csecurity');
    expect(url).not.toContain('token=');
    expect(url).not.toContain('api_key=');

    const headers = new Headers(init.headers);
    expect(headers.get('Authorization')).toBe('Bearer jwt-token-value');
    expect(headers.get('Accept')).toBe('text/event-stream');
    expect(onConnect).toHaveBeenCalledTimes(1);

    unsubscribe();
  });
});
