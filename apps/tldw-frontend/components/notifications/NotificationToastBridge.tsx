import React, { useCallback, useEffect, useRef } from 'react';

import { useToast } from '@web/components/ui/ToastProvider';
import {
  listNotifications,
  subscribeNotificationsStream,
  type NotificationItem,
  type NotificationStreamEvent,
} from '@web/lib/api/notifications';

const TOAST_COALESCE_MS = 800;

function severityToVariant(severity?: string): 'info' | 'success' | 'warning' | 'danger' {
  if (severity === 'error') return 'danger';
  if (severity === 'warning') return 'warning';
  return 'info';
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

export function NotificationToastBridge() {
  const { show } = useToast();
  const cursorRef = useRef(0);
  const pendingToastCountRef = useRef(0);
  const latestToastItemRef = useRef<NotificationItem | null>(null);
  const toastTimerRef = useRef<number | null>(null);

  const flushQueuedToast = useCallback(() => {
    const burstCount = pendingToastCountRef.current;
    const latestItem = latestToastItemRef.current;
    pendingToastCountRef.current = 0;
    latestToastItemRef.current = null;
    toastTimerRef.current = null;
    if (burstCount <= 0) return;

    if (burstCount === 1 && latestItem) {
      show({
        title: latestItem.title || 'New notification',
        description: latestItem.message || 'A new notification is available.',
        variant: severityToVariant(String(latestItem.severity)),
      });
      return;
    }

    show({
      title: `${burstCount} new notifications`,
      description: 'Your inbox has been updated.',
      variant: 'info',
    });
  }, [show]);

  const queueToast = useCallback(
    (item: NotificationItem | null, incrementBy: number = 1) => {
      if (item) {
        latestToastItemRef.current = item;
      }
      pendingToastCountRef.current += Math.max(1, incrementBy);
      if (toastTimerRef.current !== null) return;
      toastTimerRef.current = window.setTimeout(() => flushQueuedToast(), TOAST_COALESCE_MS);
    },
    [flushQueuedToast]
  );

  useEffect(() => {
    let cancelled = false;
    let unsubscribe = () => {};

    void (async () => {
      try {
        const latest = await listNotifications({ limit: 1, offset: 0, include_archived: false });
        if (cancelled) {
          return;
        }
        cursorRef.current = latest.items.reduce(
          (maxId, item) => Math.max(maxId, Number(item.id) || 0),
          cursorRef.current
        );
      } catch {
        if (cancelled) {
          return;
        }
      }

      unsubscribe = subscribeNotificationsStream({
        after: cursorRef.current,
        onEvent: (event: NotificationStreamEvent) => {
          if (typeof event.id === 'number' && Number.isFinite(event.id)) {
            cursorRef.current = Math.max(cursorRef.current, event.id);
          }
          if (event.event === 'notification') {
            const nextItem = toNotificationFromStream(event.payload);
            if (nextItem) {
              queueToast(nextItem, 1);
            }
            return;
          }
          if (event.event === 'notifications_coalesced') {
            const payload = event.payload as Record<string, unknown> | undefined;
            const count = Number(payload?.count ?? 0);
            if (Number.isFinite(count) && count > 0) {
              queueToast(null, count);
            }
          }
        },
        onError: () => {
          // The notifications stream reconnects internally; no UI action needed here.
        },
      });
    })();

    return () => {
      cancelled = true;
      unsubscribe();
      if (toastTimerRef.current !== null) {
        window.clearTimeout(toastTimerRef.current);
      }
    };
  }, [queueToast]);

  return null;
}
