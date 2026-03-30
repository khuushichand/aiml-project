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

const shouldUseCookieCredentials = (headers: Record<string, string>): boolean => {
  return !headers.Authorization && !headers["X-API-KEY"]
}

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
  const useCookieCredentials = shouldUseCookieCredentials(headers)

  let cursor = after
  try {
    await streamStructuredSSE(
      url,
      {
        method: "GET",
        headers,
        credentials: useCookieCredentials ? "include" : "omit",
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
  const headers = buildAuthHeaders("GET")
  return apiClient.get<NotificationsListResponse>(
    `/notifications${buildNotificationsQueryShared({
      limit: params?.limit ?? 100,
      offset: params?.offset ?? 0,
      include_archived: params?.include_archived ?? false
    })}`,
    { withCredentials: shouldUseCookieCredentials(headers) }
  )
}

export async function getUnreadCount(): Promise<NotificationsUnreadCountResponse> {
  const headers = buildAuthHeaders("GET")
  return apiClient.get<NotificationsUnreadCountResponse>("/notifications/unread-count", {
    withCredentials: shouldUseCookieCredentials(headers)
  })
}

export async function markNotificationsRead(ids: number[]): Promise<{ updated: number }> {
  const headers = buildAuthHeaders("POST")
  return apiClient.post<{ updated: number }>("/notifications/mark-read", { ids }, {
    withCredentials: shouldUseCookieCredentials(headers)
  })
}

export async function dismissNotification(notificationId: number): Promise<{ dismissed: boolean }> {
  const headers = buildAuthHeaders("POST")
  return apiClient.post<{ dismissed: boolean }>(
    `/notifications/${notificationId}/dismiss`,
    undefined,
    {
      withCredentials: shouldUseCookieCredentials(headers)
    }
  )
}

export async function snoozeNotification(
  notificationId: number,
  minutes: number
): Promise<NotificationSnoozeResponse> {
  const headers = buildAuthHeaders("POST")
  return apiClient.post<NotificationSnoozeResponse>(`/notifications/${notificationId}/snooze`, {
    minutes
  }, {
    withCredentials: shouldUseCookieCredentials(headers)
  })
}
