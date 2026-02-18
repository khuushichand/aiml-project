import React from "react"
import {
  getServerCapabilities,
  type ServerCapabilities
} from "@/services/tldw/server-capabilities"

type UseServerCapabilitiesResult = {
  capabilities: ServerCapabilities | null
  loading: boolean
  refresh: () => Promise<void>
}

export const useServerCapabilities = (): UseServerCapabilitiesResult => {
  const [capabilities, setCapabilities] =
    React.useState<ServerCapabilities | null>(null)
  const [loading, setLoading] = React.useState<boolean>(true)
  const mountedRef = React.useRef(true)

  React.useEffect(() => {
    return () => {
      mountedRef.current = false
    }
  }, [])

  const fetchCapabilities = React.useCallback(
    async (forceRefresh: boolean) => {
      if (mountedRef.current) {
        setLoading(true)
      }

      try {
        const caps = await getServerCapabilities(
          forceRefresh ? { forceRefresh: true } : undefined
        )
        if (mountedRef.current) {
          setCapabilities(caps)
        }
      } catch {
        if (mountedRef.current) {
          // Keep null as a safe "unknown/unavailable" state; guardian routes
          // are treated as unavailable once loading has completed.
          setCapabilities(null)
        }
      } finally {
        if (mountedRef.current) {
          setLoading(false)
        }
      }
    },
    []
  )

  React.useEffect(() => {
    void fetchCapabilities(false)
  }, [fetchCapabilities])

  const refresh = React.useCallback(async () => {
    await fetchCapabilities(true)
  }, [fetchCapabilities])

  return { capabilities, loading, refresh }
}
