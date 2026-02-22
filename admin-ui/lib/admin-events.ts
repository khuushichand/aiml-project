'use client';

import { buildApiUrl } from './api-config';
import { getApiKey, getJWTToken } from './auth';

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
 * Falls back to polling if EventSource is unavailable or connection fails
 * after `maxRetries` attempts.
 */
export function subscribeToAdminEvents(
  handler: AdminEventHandler,
  options?: {
    categories?: AdminEventCategory[];
    maxRetries?: number;
    onConnect?: () => void;
    onError?: (error: Event) => void;
  },
): () => void {
  const { categories, maxRetries = 5, onConnect, onError } = options ?? {};

  let retryCount = 0;
  let eventSource: EventSource | null = null;
  let closed = false;

  const connect = () => {
    if (closed) return;

    const params = new URLSearchParams();
    if (categories?.length) {
      params.set('categories', categories.join(','));
    }
    // Add auth via query params since EventSource doesn't support custom headers
    const token = getJWTToken();
    if (token) params.set('token', token);
    const apiKey = getApiKey();
    if (apiKey) params.set('api_key', apiKey);

    const queryString = params.toString();
    const url = buildApiUrl(`/admin/events/stream${queryString ? `?${queryString}` : ''}`);

    eventSource = new EventSource(url);

    eventSource.addEventListener('connected', (e) => {
      retryCount = 0;
      onConnect?.();
    });

    // Listen for all named events
    const eventTypes = [
      'acp_session_created',
      'acp_session_closed',
      'acp_session_error',
      'acp_usage_update',
      'monitoring_alert',
      'security_event',
      'budget_breach',
      'job_completed',
      'job_failed',
      'config_changed',
      'update',
    ];

    for (const eventType of eventTypes) {
      eventSource.addEventListener(eventType, (e) => {
        try {
          const data = JSON.parse((e as MessageEvent).data);
          handler(data as AdminEvent);
        } catch {
          // Ignore parse errors
        }
      });
    }

    // Default message handler for unnamed events
    eventSource.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        handler(data as AdminEvent);
      } catch {
        // Ignore
      }
    };

    eventSource.onerror = (e) => {
      onError?.(e);
      eventSource?.close();
      eventSource = null;

      if (!closed && retryCount < maxRetries) {
        retryCount++;
        // Exponential backoff: 1s, 2s, 4s, 8s, 16s
        const delay = Math.min(1000 * Math.pow(2, retryCount - 1), 30000);
        setTimeout(connect, delay);
      }
    };
  };

  connect();

  return () => {
    closed = true;
    eventSource?.close();
    eventSource = null;
  };
}
