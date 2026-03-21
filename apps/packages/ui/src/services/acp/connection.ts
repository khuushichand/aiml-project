import type { TldwConfig } from "@/services/tldw/TldwApiClient"

import type { ACPClientConfig } from "./client"

export const DEFAULT_ACP_SERVER_URL = "http://127.0.0.1:8000"

export const resolveACPServerUrl = (config: TldwConfig | null | undefined): string =>
  typeof config?.serverUrl === "string" && config.serverUrl.trim().length > 0
    ? config.serverUrl
    : DEFAULT_ACP_SERVER_URL

export const buildACPAuthHeaders = (
  config: TldwConfig | null | undefined,
  options: { includeContentType?: boolean } = {}
): Record<string, string> => {
  const headers: Record<string, string> = {}

  if (options.includeContentType) {
    headers["Content-Type"] = "application/json"
  }

  if (config?.authMode === "single-user" && config.apiKey) {
    headers["X-API-KEY"] = config.apiKey
  } else if (config?.authMode === "multi-user" && config.accessToken) {
    headers.Authorization = `Bearer ${config.accessToken}`
  }

  if (typeof config?.orgId === "number") {
    headers["X-TLDW-Org-Id"] = String(config.orgId)
  }

  return headers
}

export const buildACPAuthParams = (
  config: TldwConfig | null | undefined
): { token?: string; api_key?: string } => ({
  token:
    config?.authMode === "multi-user" && config.accessToken
      ? config.accessToken
      : undefined,
  api_key:
    config?.authMode === "single-user" && config.apiKey
      ? config.apiKey
      : undefined,
})

export const buildACPClientConfig = (
  config: TldwConfig | null | undefined
): ACPClientConfig => ({
  serverUrl: resolveACPServerUrl(config),
  getAuthHeaders: async () => buildACPAuthHeaders(config),
  getAuthParams: async () => buildACPAuthParams(config),
})
