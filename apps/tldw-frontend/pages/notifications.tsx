import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/router';
import { useToast } from '@web/components/ui/ToastProvider';
import {
  dismissNotification,
  getUnreadCount,
  getNotificationPreferences,
  updateNotificationPreferences,
  listNotifications,
  markNotificationsRead,
  NotificationItem,
  NotificationPreferences,
  NotificationStreamEvent,
  snoozeNotification,
  subscribeNotificationsStream,
} from '@web/lib/api/notifications';
import { formatRelativeTime } from '@web/lib/utils';

const POLL_INTERVAL_MS = 30_000;
const DEFAULT_SNOOZE_MINUTES = 15;

function resolveRouteForLinkType(linkType: string | null | undefined): string | undefined {
  if (!linkType) return undefined
  const lt = linkType.toLowerCase()
  if (lt.includes("reading")) return "/collections"
  if (lt.includes("note") || lt.includes("document")) return "/notes"
  if (lt.includes("watchlist") || lt.includes("job")) return "/watchlists"
  return undefined
}

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
  const [snoozedItems, setSnoozedItems] = useState<NotificationItem[]>([]);
  const [showSnoozed, setShowSnoozed] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const cursorRef = useRef(0);
  const [showPrefs, setShowPrefs] = useState(false);
  const [prefs, setPrefs] = useState<NotificationPreferences | null>(null);
  const [prefsLoading, setPrefsLoading] = useState(false);

  const refreshInbox = useCallback(async () => {
    try {
      const [list, archived, unread] = await Promise.all([
        listNotifications({ limit: 100, offset: 0, include_archived: false }),
        listNotifications({ limit: 50, offset: 0, include_archived: true }),
        getUnreadCount(),
      ]);
      setItems(list.items);
      // Snoozed = archived items that have dismissed_at set (snoozed, not just dismissed)
      const activeIds = new Set(list.items.map((i) => i.id));
      setSnoozedItems(archived.items.filter((i) => i.dismissed_at && !activeIds.has(i.id)));
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

  const loadPrefs = useCallback(async () => {
    setPrefsLoading(true);
    try {
      const p = await getNotificationPreferences();
      setPrefs(p);
    } catch {
      // Preferences may not be available (e.g., single-user mode without auth)
    } finally {
      setPrefsLoading(false);
    }
  }, []);

  const togglePref = useCallback(
    async (key: 'reminder_enabled' | 'job_completed_enabled' | 'job_failed_enabled') => {
      if (!prefs) return;
      const updated = { [key]: !prefs[key] };
      try {
        const result = await updateNotificationPreferences(updated);
        setPrefs(result);
      } catch {
        show({ title: 'Failed to update preference', variant: 'danger' });
      }
    },
    [prefs, show]
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
            <div className="flex gap-2">
              <button
                type="button"
                className="rounded border border-border px-3 py-2 text-sm font-medium hover:bg-muted"
                onClick={() => void refreshInbox()}
              >
                Refresh
              </button>
              <button
                type="button"
                className="rounded border border-border px-3 py-2 text-sm font-medium hover:bg-muted"
                onClick={() => { setShowPrefs(!showPrefs); if (!prefs) void loadPrefs(); }}
                aria-expanded={showPrefs}
              >
                {showPrefs ? 'Hide Preferences' : 'Preferences'}
              </button>
            </div>
          </header>

          {showPrefs && (
            <div className="mb-4 rounded-lg border border-border bg-muted/30 p-4">
              <h3 className="mb-3 text-sm font-semibold">Notification Preferences</h3>
              {prefsLoading || !prefs ? (
                <p className="text-sm text-muted-foreground">Loading preferences...</p>
              ) : (
                <div className="space-y-3">
                  {([
                    { key: 'job_completed_enabled' as const, label: 'Job completed notifications', desc: 'Notify when watchlist jobs finish successfully' },
                    { key: 'job_failed_enabled' as const, label: 'Job failed notifications', desc: 'Notify when watchlist jobs encounter errors' },
                    { key: 'reminder_enabled' as const, label: 'Reminder notifications', desc: 'Notify when snoozed items resurface' },
                  ]).map(({ key, label, desc }) => (
                    <label key={key} className="flex items-start gap-3 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={prefs[key]}
                        onChange={() => void togglePref(key)}
                        className="mt-1 h-4 w-4 rounded border-border"
                      />
                      <div>
                        <span className="text-sm font-medium">{label}</span>
                        <p className="text-xs text-muted-foreground">{desc}</p>
                      </div>
                    </label>
                  ))}
                </div>
              )}
            </div>
          )}

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
                    {(item.link_url || resolveRouteForLinkType(item.link_type)) && (
                      <button
                        type="button"
                        className="rounded bg-primary/10 border border-primary/30 px-2 py-1 text-xs font-medium text-primary hover:bg-primary/20"
                        onClick={async () => {
                          if (!item.read_at) {
                            try { await handleMarkRead(item.id) } catch { /* navigate anyway */ }
                          }
                          if (item.link_url) {
                            try {
                              const url = new URL(item.link_url, window.location.origin)
                              if (url.origin === window.location.origin) {
                                void router.push(url.pathname + url.search + url.hash)
                              }
                            } catch { /* malformed URL — ignore */ }
                          } else {
                            const route = resolveRouteForLinkType(item.link_type)
                            if (route) void router.push(route)
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

          {snoozedItems.length > 0 && (
            <div className="mt-6 border-t border-border pt-4">
              <button
                type="button"
                className="mb-3 text-sm font-medium text-muted-foreground hover:text-foreground"
                onClick={() => setShowSnoozed(!showSnoozed)}
              >
                {showSnoozed ? 'Hide' : 'Show'} snoozed ({snoozedItems.length})
              </button>
              {showSnoozed && (
                <ul className="space-y-2">
                  {snoozedItems.map((item) => (
                    <li key={item.id} className="rounded border border-border/50 bg-muted/20 p-3 opacity-70">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <h2 className="text-sm font-medium text-muted-foreground">{item.title}</h2>
                          <p className="mt-1 text-xs text-muted-foreground">{item.message}</p>
                        </div>
                        <span className="whitespace-nowrap text-xs text-muted-foreground">
                          Snoozed {item.dismissed_at ? formatRelativeTime(item.dismissed_at) : ''}
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </section>
    </div>
  );
}
