import React from "react"
import { useStorage } from "@plasmohq/storage/hook"

import { tldwClient, type TldwConfig } from "@/services/tldw/TldwApiClient"

const DEFAULT_SERVER_URL = "http://127.0.0.1:8000"

const normalizeConnectionConfig = (
  config: TldwConfig | null | undefined,
  fallback: TldwConfig
): TldwConfig => ({
  serverUrl:
    typeof config?.serverUrl === "string" && config.serverUrl.trim().length > 0
      ? config.serverUrl
      : fallback.serverUrl,
  authMode:
    config?.authMode === "multi-user" || config?.authMode === "single-user"
      ? config.authMode
      : fallback.authMode,
  apiKey: config?.apiKey ?? fallback.apiKey,
  accessToken: config?.accessToken ?? fallback.accessToken,
  refreshToken: config?.refreshToken ?? fallback.refreshToken,
  orgId: typeof config?.orgId === "number" ? config.orgId : fallback.orgId
})

export const useCanonicalConnectionConfig = (): {
  config: TldwConfig | null
  loading: boolean
} => {
  const [legacyServerUrl] = useStorage("serverUrl", DEFAULT_SERVER_URL)
  const [legacyAuthMode] = useStorage("authMode", "single-user")
  const [legacyApiKey] = useStorage("apiKey", "")
  const [legacyAccessToken] = useStorage("accessToken", "")

  const fallbackConfig = React.useMemo<TldwConfig>(
    () => ({
      serverUrl:
        typeof legacyServerUrl === "string" && legacyServerUrl.trim().length > 0
          ? legacyServerUrl
          : DEFAULT_SERVER_URL,
      authMode: legacyAuthMode === "multi-user" ? "multi-user" : "single-user",
      apiKey: legacyApiKey || undefined,
      accessToken: legacyAccessToken || undefined
    }),
    [legacyAccessToken, legacyApiKey, legacyAuthMode, legacyServerUrl]
  )

  const [config, setConfig] = React.useState<TldwConfig | null>(null)
  const [loading, setLoading] = React.useState(true)

  React.useEffect(() => {
    let cancelled = false

    const resolveConfig = async () => {
      setLoading(true)
      try {
        const canonicalConfig = await tldwClient.getConfig()
        if (!cancelled) {
          setConfig(normalizeConnectionConfig(canonicalConfig, fallbackConfig))
        }
      } catch {
        if (!cancelled) {
          setConfig(fallbackConfig)
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void resolveConfig()

    return () => {
      cancelled = true
    }
  }, [fallbackConfig])

  return { config, loading }
}
