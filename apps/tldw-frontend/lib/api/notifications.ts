import { buildAuthHeaders, getApiBaseUrl, apiClient } from "@web/lib/api"
import { streamStructuredSSE } from "@web/lib/sse"
import {
  buildNotificationsQuery as buildNotificationsQueryShared,
  createNotificationStreamSubscription as createNotificationStreamSubscriptionShared
} from "@/services/notifications"
import type {
  NotificationItem,
  NotificationSeverity,
  NotificationSnoozeResponse,
  NotificationStreamEvent,
  NotificationsListResponse,
  NotificationsUnreadCountResponse,
  SubscribeNotificationsOptions
} from "@/services/notifications"

export type {
  NotificationItem,
  NotificationSeverity,
  NotificationSnoozeResponse,
  NotificationStreamEvent,
  NotificationsListResponse,
  NotificationsUnreadCountResponse,
  SubscribeNotificationsOptions
} from "@/services/notifications"

async function readNotificationsStream(
  signal: AbortSignal,
  after: number,
  onEvent: (event: NotificationStreamEvent) => void
): Promise<number> {
  const baseUrl = getApiBaseUrl().replace(/\/$/, "")
  const url = `${baseUrl}/notifications/stream${buildNotificationsQueryShared({ after })}`
  const headers = buildAuthHeaders("GET")
  if (after > 0) {
    headers["Last-Event-ID"] = String(after)
  }

  let cursor = after
  try {
    await streamStructuredSSE(
      url,
      {
        method: "GET",
        headers,
        credentials: "include",
        signal
      },
      (event) => {
        onEvent(event)
        if (typeof event.id === "number" && Number.isFinite(event.id) && event.id > cursor) {
          cursor = event.id
        }
      }
    )
    return cursor
  } catch (error) {
    if (error && typeof error === "object") {
      ;(error as { cursor?: number }).cursor = cursor
    }
    throw error
  }
}

export function subscribeNotificationsStream(options: SubscribeNotificationsOptions): () => void {
  return createNotificationStreamSubscriptionShared({
    ...options,
    readStream: readNotificationsStream
  })
}

export async function listNotifications(params?: {
  limit?: number
  offset?: number
  include_archived?: boolean
}): Promise<NotificationsListResponse> {
  return apiClient.get<NotificationsListResponse>(
    `/notifications${buildNotificationsQueryShared({
      limit: params?.limit ?? 100,
      offset: params?.offset ?? 0,
      include_archived: params?.include_archived ?? false
    })}`
  )
}

export async function getUnreadCount(): Promise<NotificationsUnreadCountResponse> {
  return apiClient.get<NotificationsUnreadCountResponse>("/notifications/unread-count")
}

export async function markNotificationsRead(ids: number[]): Promise<{ updated: number }> {
  return apiClient.post<{ updated: number }>("/notifications/mark-read", { ids })
}

export async function dismissNotification(notificationId: number): Promise<{ dismissed: boolean }> {
  return apiClient.post<{ dismissed: boolean }>(`/notifications/${notificationId}/dismiss`)
}

export async function snoozeNotification(
  notificationId: number,
  minutes: number
): Promise<NotificationSnoozeResponse> {
  return apiClient.post<NotificationSnoozeResponse>(`/notifications/${notificationId}/snooze`, {
    minutes
  })
}
