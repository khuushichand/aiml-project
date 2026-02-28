import { buildAuthHeaders, getApiBaseUrl, apiClient } from '@web/lib/api';
import { captureSessionIdFromHeaders } from '@web/lib/session';

export type NotificationSeverity = 'info' | 'warning' | 'error';

export interface NotificationItem {
  id: number;
  kind: string;
  title: string;
  message: string;
  severity: NotificationSeverity | string;
  created_at: string;
  read_at?: string | null;
  dismissed_at?: string | null;
}

export interface NotificationsListResponse {
  items: NotificationItem[];
  total: number;
}

export interface NotificationsUnreadCountResponse {
  unread_count: number;
}

export interface NotificationSnoozeResponse {
  task_id: string;
  run_at: string;
}

export interface NotificationStreamEvent {
  event: string;
  id?: number;
  payload?: unknown;
}

export interface SubscribeNotificationsOptions {
  after?: number;
  reconnectDelayMs?: number;
  onEvent: (event: NotificationStreamEvent) => void;
  onError?: (error: unknown) => void;
}

const DEFAULT_RECONNECT_DELAY_MS = 1200;

function toQuery(params: Record<string, string | number | boolean | undefined>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null) return;
    search.set(key, String(value));
  });
  const encoded = search.toString();
  return encoded ? `?${encoded}` : '';
}

async function readNotificationsStream(
  signal: AbortSignal,
  after: number,
  onEvent: (event: NotificationStreamEvent) => void
): Promise<number> {
  const baseUrl = getApiBaseUrl().replace(/\/$/, '');
  const url = `${baseUrl}/notifications/stream${toQuery({ after })}`;
  const headers = buildAuthHeaders('GET');
  if (after > 0) {
    headers['Last-Event-ID'] = String(after);
  }

  const response = await fetch(url, {
    method: 'GET',
    headers,
    credentials: 'include',
    signal,
  });
  captureSessionIdFromHeaders(response.headers);
  if (!response.ok || !response.body) {
    throw new Error(`notifications stream failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';
  let cursor = after;
  let eventType = 'message';
  let eventId: number | undefined;
  let dataLines: string[] = [];

  const flushFrame = () => {
    if (!eventType && dataLines.length === 0 && eventId === undefined) {
      return;
    }
    let payload: unknown = undefined;
    if (dataLines.length > 0) {
      const raw = dataLines.join('\n');
      try {
        payload = JSON.parse(raw);
      } catch {
        payload = raw;
      }
    }
    onEvent({
      event: eventType || 'message',
      id: eventId,
      payload,
    });
    if (typeof eventId === 'number' && Number.isFinite(eventId) && eventId > cursor) {
      cursor = eventId;
    }
    eventType = 'message';
    eventId = undefined;
    dataLines = [];
  };

  while (!signal.aborted) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';
    for (const rawLine of lines) {
      const line = rawLine.endsWith('\r') ? rawLine.slice(0, -1) : rawLine;
      if (line === '') {
        flushFrame();
        continue;
      }
      if (line.startsWith(':')) {
        continue;
      }
      if (line.startsWith('event:')) {
        eventType = line.slice(6).trim() || 'message';
        continue;
      }
      if (line.startsWith('id:')) {
        const parsed = Number.parseInt(line.slice(3).trim(), 10);
        eventId = Number.isFinite(parsed) ? parsed : undefined;
        continue;
      }
      if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trim());
      }
    }
  }

  if (buffer.trim().length > 0) {
    dataLines.push(buffer.trim());
  }
  flushFrame();
  return cursor;
}

export function subscribeNotificationsStream(options: SubscribeNotificationsOptions): () => void {
  const controller = new AbortController();
  let cursor = Math.max(0, options.after ?? 0);
  const reconnectDelayMs = Math.max(250, options.reconnectDelayMs ?? DEFAULT_RECONNECT_DELAY_MS);

  const run = async () => {
    while (!controller.signal.aborted) {
      try {
        cursor = await readNotificationsStream(controller.signal, cursor, options.onEvent);
      } catch (error) {
        if (controller.signal.aborted) break;
        options.onError?.(error);
        await new Promise((resolve) => setTimeout(resolve, reconnectDelayMs));
      }
    }
  };

  void run();
  return () => controller.abort();
}

export async function listNotifications(params?: {
  limit?: number;
  offset?: number;
  include_archived?: boolean;
}): Promise<NotificationsListResponse> {
  return apiClient.get<NotificationsListResponse>(
    `/notifications${toQuery({
      limit: params?.limit ?? 100,
      offset: params?.offset ?? 0,
      include_archived: params?.include_archived ?? false,
    })}`
  );
}

export async function getUnreadCount(): Promise<NotificationsUnreadCountResponse> {
  return apiClient.get<NotificationsUnreadCountResponse>('/notifications/unread-count');
}

export async function markNotificationsRead(ids: number[]): Promise<{ updated: number }> {
  return apiClient.post<{ updated: number }>('/notifications/mark-read', { ids });
}

export async function dismissNotification(notificationId: number): Promise<{ dismissed: boolean }> {
  return apiClient.post<{ dismissed: boolean }>(`/notifications/${notificationId}/dismiss`);
}

export async function snoozeNotification(
  notificationId: number,
  minutes: number
): Promise<NotificationSnoozeResponse> {
  return apiClient.post<NotificationSnoozeResponse>(`/notifications/${notificationId}/snooze`, {
    minutes,
  });
}
