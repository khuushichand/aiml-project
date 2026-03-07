'use client';

import { buildAuthHeaders, buildProxyUrl } from './http';

export type AdminEventCategory = 'acp' | 'monitoring' | 'security' | 'budget' | 'jobs' | 'system';

export interface AdminEvent {
  event: string;
  category: AdminEventCategory;
  data: Record<string, unknown>;
  timestamp: string;
}

export type AdminEventHandler = (event: AdminEvent) => void;

/**
 * Create a Server-Sent Events connection to the admin events stream.
 *
 * Returns a cleanup function that closes the connection.
 *
 * Uses streaming `fetch` with auth headers and reconnects with exponential
 * backoff up to `maxRetries` attempts.
 */
export function subscribeToAdminEvents(
  handler: AdminEventHandler,
  options?: {
    categories?: AdminEventCategory[];
    maxRetries?: number;
    onConnect?: () => void;
    onError?: (error: unknown) => void;
  },
): () => void {
  const { categories, maxRetries = 5, onConnect, onError } = options ?? {};

  let retryCount = 0;
  let reconnectTimer: number | null = null;
  let abortController: AbortController | null = null;
  let closed = false;

  const parseSseFrame = (frame: string): AdminEvent | null => {
    const normalized = frame.replace(/\r\n/g, '\n').trim();
    if (!normalized || normalized.startsWith(':')) return null;

    const lines = normalized.split('\n');
    const dataLines: string[] = [];

    for (const line of lines) {
      if (!line || line.startsWith(':')) continue;

      const separatorIndex = line.indexOf(':');
      const field = separatorIndex === -1 ? line : line.slice(0, separatorIndex);
      let value = separatorIndex === -1 ? '' : line.slice(separatorIndex + 1);
      if (value.startsWith(' ')) value = value.slice(1);

      if (field === 'data') {
        dataLines.push(value);
      }
    }

    if (dataLines.length === 0) return null;

    try {
      const payload = JSON.parse(dataLines.join('\n'));
      return payload as AdminEvent;
    } catch {
      return null;
    }
  };

  const readEventStream = async (stream: ReadableStream<Uint8Array>, signal: AbortSignal): Promise<void> => {
    const reader = stream.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (!signal.aborted) {
        const { value, done } = await reader.read();
        if (done) break;
        if (!value) continue;

        buffer += decoder.decode(value, { stream: true });
        buffer = buffer.replace(/\r\n/g, '\n');

        let boundaryIndex = buffer.indexOf('\n\n');
        while (boundaryIndex !== -1) {
          const frame = buffer.slice(0, boundaryIndex);
          buffer = buffer.slice(boundaryIndex + 2);
          const event = parseSseFrame(frame);
          if (event) handler(event);
          boundaryIndex = buffer.indexOf('\n\n');
        }
      }

      buffer += decoder.decode();
      const trailingEvent = parseSseFrame(buffer);
      if (trailingEvent) handler(trailingEvent);
    } finally {
      reader.releaseLock();
    }
  };

  const scheduleReconnect = () => {
    if (closed || retryCount >= maxRetries) return;
    retryCount += 1;
    const delay = Math.min(1000 * Math.pow(2, retryCount - 1), 30000);
    reconnectTimer = window.setTimeout(() => {
      reconnectTimer = null;
      void connect();
    }, delay);
  };

  const connect = async () => {
    if (closed) return;

    const params = new URLSearchParams();
    if (categories?.length) {
      params.set('categories', categories.join(','));
    }
    const queryString = params.toString();
    const url = buildProxyUrl(`/admin/events/stream${queryString ? `?${queryString}` : ''}`);

    const headers = new Headers(buildAuthHeaders('GET'));
    headers.set('Accept', 'text/event-stream');

    abortController = new AbortController();

    try {
      const response = await fetch(url, {
        method: 'GET',
        headers,
        cache: 'no-store',
        credentials: 'include',
        signal: abortController.signal,
      });

      if (!response.ok || !response.body) {
        throw new Error(`Admin event stream connection failed with status ${response.status}`);
      }

      retryCount = 0;
      onConnect?.();

      await readEventStream(response.body, abortController.signal);
      if (!closed) {
        scheduleReconnect();
      }
    } catch (error) {
      if (!closed) {
        onError?.(error);
        scheduleReconnect();
      }
    }
  };

  void connect();

  return () => {
    closed = true;
    if (reconnectTimer !== null) {
      window.clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    abortController?.abort();
    abortController = null;
  };
}
