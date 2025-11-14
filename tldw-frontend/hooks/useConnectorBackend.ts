import { useEffect, useState } from 'react'
import { getApiBaseUrl, buildAuthHeaders } from '@/lib/api'

/**
 * Preflight check for the Connectors backend.
 * - Pings the providers endpoint. If 404, marks notEnabled=true.
 * - Otherwise invokes the provided onEnabled callback.
 * - Uses a cancellation flag to avoid state updates after unmount.
 */
export function useConnectorBackend(onEnabled: () => void | Promise<void>) {
  const [notEnabled, setNotEnabled] = useState(false)

  useEffect(() => {
    let cancelled = false

    const ping = async () => {
      try {
        const url = `${getApiBaseUrl()}/connectors/providers`
        const resp = await fetch(url, { headers: buildAuthHeaders('GET') })
        if (cancelled) return

        if (resp.status === 404) {
          setNotEnabled(true)
          return
        }
        await onEnabled()
      } catch {
        // Network or CORS issues: still attempt to run the page's loader
        if (!cancelled) {
          await onEnabled()
        }
      }
    }

    ping()
    return () => { cancelled = true }
  }, [onEnabled])

  return { notEnabled }
}

