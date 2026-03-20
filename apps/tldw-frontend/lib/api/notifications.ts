import { buildAuthHeaders, getApiBaseUrl, apiClient } from '@web/lib/api';
import { streamStructuredSSE } from '@web/lib/sse';

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

  let cursor = after;
  await streamStructuredSSE(
    url,
    {
      method: 'GET',
      headers,
      credentials: 'include',
      signal,
    },
    (event) => {
      onEvent(event);
      if (typeof event.id === 'number' && Number.isFinite(event.id) && event.id > cursor) {
        cursor = event.id;
      }
    }
  );
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
