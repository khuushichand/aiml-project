/**
 * Background notification subscription for the browser extension.
 *
 * Subscribes to the server's SSE notification stream and:
 * 1. Updates a storage-backed unread count for the UI bell icon
 * 2. Shows Chrome system notifications for new items
 *
 * Designed to run in the background service worker context.
 */

import { subscribeNotificationsStream, getUnreadCount } from "@/services/notifications"
import type { NotificationStreamEvent } from "@/services/notifications"
import { notify } from "@/services/background-helpers"
import { createSafeStorage } from "@/utils/safe-storage"

const UNREAD_COUNT_KEY = "tldw:notifications:unreadCount"
const SUBSCRIPTION_ACTIVE_KEY = "tldw:notifications:subscriptionActive"

let unsubscribe: (() => void) | null = null

/**
 * Start listening for notifications from the server.
 * Safe to call multiple times — only one subscription is active at a time.
 */
export async function startNotificationSubscription(): Promise<void> {
  if (unsubscribe) return // Already subscribed

  const storage = createSafeStorage()

  // Fetch initial unread count
  try {
    const { unread_count } = await getUnreadCount()
    await storage.set(UNREAD_COUNT_KEY, unread_count)
  } catch {
    // Server may not be reachable yet
  }

  // Subscribe to SSE stream
  try {
    unsubscribe = subscribeNotificationsStream({
      onEvent: async (event: NotificationStreamEvent) => {
        if (event.event === "notification") {
          // Show Chrome system notification
          const payload = event.payload as {
            title?: string
            message?: string
            severity?: string
          } | null
          if (payload?.title) {
            notify(payload.title, payload.message || "")
          }

          // Increment unread count
          const current = (await storage.get<number>(UNREAD_COUNT_KEY)) ?? 0
          await storage.set(UNREAD_COUNT_KEY, current + 1)
        }

        if (event.event === "notifications_coalesced") {
          // Batch arrived — refresh full count
          try {
            const { unread_count } = await getUnreadCount()
            await storage.set(UNREAD_COUNT_KEY, unread_count)
          } catch {
            // Ignore
          }
        }
      },
      onError: () => {
        // Stream will auto-reconnect (handled by subscribeNotificationsStream)
      },
    })

    await storage.set(SUBSCRIPTION_ACTIVE_KEY, true)
  } catch {
    // Server not available — will retry on next init
  }
}

/**
 * Stop the notification subscription.
 */
export function stopNotificationSubscription(): void {
  if (unsubscribe) {
    unsubscribe()
    unsubscribe = null
  }
}

/**
 * Get the current unread count from storage (for UI components).
 */
export async function getStoredUnreadCount(): Promise<number> {
  const storage = createSafeStorage()
  return (await storage.get<number>(UNREAD_COUNT_KEY)) ?? 0
}

/**
 * Reset the unread count (e.g., when user opens notifications page).
 */
export async function resetStoredUnreadCount(): Promise<void> {
  const storage = createSafeStorage()
  await storage.set(UNREAD_COUNT_KEY, 0)
}
