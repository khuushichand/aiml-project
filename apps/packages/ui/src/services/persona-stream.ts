import type { TldwConfig } from "@/services/tldw/TldwApiClient"
import { resolveBrowserWebSocketBase } from "@/services/tldw/browser-websocket"

export const buildPersonaWebSocketUrl = (
  config: Pick<TldwConfig, "serverUrl" | "authMode" | "apiKey" | "accessToken">
): string => {
  const serverUrl = String(config.serverUrl || "").trim()
  if (!serverUrl) {
    throw new Error("tldw server is not configured")
  }

  const base = resolveBrowserWebSocketBase(serverUrl)
  const params = new URLSearchParams()

  if (config.authMode === "multi-user") {
    const token = String(config.accessToken || "").trim()
    if (!token) {
      throw new Error("Not authenticated. Please log in under Settings.")
    }
    params.set("token", token)
  } else {
    const apiKey = String(config.apiKey || "").trim()
    if (!apiKey) {
      throw new Error("API key missing. Update Settings -> tldw server.")
    }
    params.set("api_key", apiKey)
  }

  return `${base}/api/v1/persona/stream?${params.toString()}`
}
