import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/router';
import { useToast } from '@web/components/ui/ToastProvider';
import {
  dismissNotification,
  getUnreadCount,
  listNotifications,
  markNotificationsRead,
  NotificationItem,
  NotificationStreamEvent,
  snoozeNotification,
  subscribeNotificationsStream,
} from '@web/lib/api/notifications';
import { formatRelativeTime } from '@web/lib/utils';

const POLL_INTERVAL_MS = 30_000;
const DEFAULT_SNOOZE_MINUTES = 15;

function toNotificationFromStream(payload: unknown): NotificationItem | null {
  if (!payload || typeof payload !== 'object') return null;
  const data = payload as Record<string, unknown>;
  const rawId = Number(data.notification_id ?? data.event_id);
  if (!Number.isFinite(rawId) || rawId <= 0) return null;
  return {
    id: rawId,
    kind: String(data.kind ?? 'notification'),
    title: String(data.title ?? 'Notification'),
    message: String(data.message ?? ''),
    severity: String(data.severity ?? 'info'),
    created_at: String(data.created_at ?? new Date().toISOString()),
    read_at: null,
    dismissed_at: null,
  };
}

export default function NotificationsPage() {
  const { show } = useToast();
  const router = useRouter();
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const cursorRef = useRef(0);

  const refreshInbox = useCallback(async () => {
    try {
      const [list, unread] = await Promise.all([
        listNotifications({ limit: 100, offset: 0, include_archived: false }),
        getUnreadCount(),
      ]);
      setItems(list.items);
      setUnreadCount(unread.unread_count);
      const maxSeen = list.items.reduce((maxId, item) => Math.max(maxId, item.id), cursorRef.current);
      cursorRef.current = maxSeen;
      setError(null);
    } catch (refreshError) {
      const message = refreshError instanceof Error ? refreshError.message : 'Failed to load notifications';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const handleSnooze = useCallback(
    async (notificationId: number, minutes: number = DEFAULT_SNOOZE_MINUTES) => {
      try {
        await snoozeNotification(notificationId, minutes);
        show({
          title: 'Snoozed',
          description: `We will remind you again in ${minutes} minutes.`,
          variant: 'success',
        });
      } catch (snoozeError) {
        const message = snoozeError instanceof Error ? snoozeError.message : 'Failed to snooze notification';
        show({
          title: 'Snooze failed',
          description: message,
          variant: 'danger',
        });
      }
    },
    [show]
  );

  const applyIncomingNotification = useCallback(
    (incoming: NotificationItem) => {
      setItems((previous) => {
        if (previous.some((item) => item.id === incoming.id)) {
          return previous;
        }
        return [incoming, ...previous].slice(0, 200);
      });
      setUnreadCount((count) => count + 1);
      cursorRef.current = Math.max(cursorRef.current, incoming.id);
    },
    []
  );

  useEffect(() => {
    void refreshInbox();
  }, [refreshInbox]);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      void refreshInbox();
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(intervalId);
  }, [refreshInbox]);

  useEffect(() => {
    const unsubscribe = subscribeNotificationsStream({
      after: cursorRef.current,
      onEvent: (event: NotificationStreamEvent) => {
        if (typeof event.id === 'number' && Number.isFinite(event.id)) {
          cursorRef.current = Math.max(cursorRef.current, event.id);
        }
        if (event.event === 'notification') {
          const nextItem = toNotificationFromStream(event.payload);
          if (nextItem) {
            applyIncomingNotification(nextItem);
          }
          return;
        }
        if (event.event === 'notifications_coalesced') {
          void refreshInbox();
          return;
        }
        if (event.event === 'reset_required') {
          void refreshInbox();
        }
      },
      onError: () => {
        // Polling remains active as a fallback path.
      },
    });
    return () => {
      unsubscribe();
    };
  }, [applyIncomingNotification, refreshInbox]);

  const handleMarkRead = useCallback(async (notificationId: number) => {
    try {
      await markNotificationsRead([notificationId]);
      setItems((previous) =>
        previous.map((item) =>
          item.id === notificationId
            ? { ...item, read_at: item.read_at || new Date().toISOString() }
            : item
        )
      );
      setUnreadCount((count) => Math.max(0, count - 1));
    } catch (markError) {
      const message = markError instanceof Error ? markError.message : 'Failed to mark notification as read';
      show({ title: 'Mark read failed', description: message, variant: 'danger' });
    }
  }, [show]);

  const handleDismiss = useCallback(async (notificationId: number) => {
    try {
      await dismissNotification(notificationId);
      setItems((previous) => {
        const target = previous.find((item) => item.id === notificationId);
        if (target && !target.read_at && !target.dismissed_at) {
          setUnreadCount((count) => Math.max(0, count - 1));
        }
        return previous.filter((item) => item.id !== notificationId);
      });
    } catch (dismissError) {
      const message = dismissError instanceof Error ? dismissError.message : 'Failed to dismiss notification';
      show({ title: 'Dismiss failed', description: message, variant: 'danger' });
    }
  }, [show]);

  const hasNotifications = items.length > 0;
  const unreadLabel = useMemo(() => `Unread: ${unreadCount}`, [unreadCount]);

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-6 sm:px-6 lg:px-8">
        <section className="rounded-lg border border-border bg-card p-4 shadow-sm">
          <header className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h1 className="text-2xl font-semibold text-foreground">Notifications</h1>
              <p className="mt-1 text-sm text-muted-foreground">{unreadLabel}</p>
            </div>
            <button
              type="button"
              className="rounded border border-border px-3 py-2 text-sm font-medium hover:bg-muted"
              onClick={() => void refreshInbox()}
            >
              Refresh
            </button>
          </header>

          {error && (
            <div className="mb-4 rounded border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
              {error}
            </div>
          )}

          {isLoading && !hasNotifications ? (
            <div className="py-8 text-center text-sm text-muted-foreground">Loading notifications...</div>
          ) : !hasNotifications ? (
            <div className="py-8 text-center text-sm text-muted-foreground">No notifications yet.</div>
          ) : (
            <ul className="space-y-3">
              {items.map((item) => (
                <li key={item.id} className="rounded border border-border/70 bg-card/80 p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h2 className="text-sm font-semibold text-foreground">{item.title}</h2>
                      <p className="mt-1 text-sm text-muted-foreground">{item.message}</p>
                    </div>
                    <span className="whitespace-nowrap text-xs text-muted-foreground">
                      {formatRelativeTime(item.created_at)}
                    </span>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {(item.link_url || item.link_type) && (
                      <button
                        type="button"
                        className="rounded bg-primary/10 border border-primary/30 px-2 py-1 text-xs font-medium text-primary hover:bg-primary/20"
                        onClick={() => {
                          void handleMarkRead(item.id)
                          if (item.link_url) {
                            try {
                              const url = new URL(item.link_url, window.location.origin)
                              if (url.origin === window.location.origin) {
                                void router.push(url.pathname + url.search + url.hash)
                              }
                            } catch {
                              // Malformed URL — ignore
                            }
                          } else if (item.link_type) {
                            const lt = (item.link_type || "").toLowerCase()
                            let route = "/companion"
                            if (lt.includes("reading")) route = "/collections"
                            else if (lt.includes("note") || lt.includes("document")) route = "/notes"
                            else if (lt.includes("watchlist") || lt.includes("job")) route = "/watchlists"
                            void router.push(route)
                          }
                        }}
                      >
                        View
                      </button>
                    )}
                    {!item.read_at && (
                      <button
                        type="button"
                        className="rounded border border-border px-2 py-1 text-xs font-medium hover:bg-muted"
                        onClick={() => void handleMarkRead(item.id)}
                      >
                        Mark read
                      </button>
                    )}
                    <button
                      type="button"
                      className="rounded border border-border px-2 py-1 text-xs font-medium hover:bg-muted"
                      onClick={() => void handleSnooze(item.id, DEFAULT_SNOOZE_MINUTES)}
                    >
                      Snooze {DEFAULT_SNOOZE_MINUTES}m
                    </button>
                    <button
                      type="button"
                      className="rounded border border-border px-2 py-1 text-xs font-medium hover:bg-muted"
                      onClick={() => void handleDismiss(item.id)}
                    >
                      Dismiss
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
    </div>
  );
}
