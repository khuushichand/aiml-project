/**
 * Hook to read the notification unread count from extension storage.
 * The count is maintained by the background notification subscription.
 *
 * Returns 0 when running outside the extension context.
 */

import { useEffect, useState } from "react"

const UNREAD_COUNT_KEY = "tldw:notifications:unreadCount"
const POLL_INTERVAL_MS = 5_000

export function useNotificationCount(): number {
  const [count, setCount] = useState(0)

  useEffect(() => {
    let cancelled = false

    const readCount = () => {
      try {
        const raw = localStorage.getItem(UNREAD_COUNT_KEY)
        if (!cancelled && raw != null) {
          setCount(Number(raw) || 0)
        }
      } catch {
        // localStorage unavailable
      }
    }

    readCount()
    const id = setInterval(readCount, POLL_INTERVAL_MS)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  return count
}
