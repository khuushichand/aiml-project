import type { TldwConfig } from "@/services/tldw/TldwApiClient"
import {
  deriveScopedUserId,
  deriveServerFingerprint
} from "@/utils/media-navigation-scope"

export type ChatSurfaceScopeInput = {
  serverUrl: string | null
  authMode: string | null
  orgId: string | number | null
  userId: string | number | null
  accessToken?: string | null
  apiKey?: string | null
}

const normalizeAuthMode = (authMode: string | null | undefined): string => {
  const normalized = String(authMode || "").trim().toLowerCase()
  return normalized || "unknown"
}

const normalizeOrgScope = (orgId: string | number | null | undefined): string => {
  if (orgId === null || typeof orgId === "undefined") {
    return "org:none"
  }
  const normalized = String(orgId).trim()
  return normalized ? `org:${normalized}` : "org:none"
}

const fnv1a36 = (value: string): string => {
  let hash = 2166136261
  for (let i = 0; i < value.length; i += 1) {
    hash ^= value.charCodeAt(i)
    hash +=
      (hash << 1) +
      (hash << 4) +
      (hash << 7) +
      (hash << 8) +
      (hash << 24)
  }
  return (hash >>> 0).toString(36)
}

const deriveSingleUserApiKeyScope = (
  authMode: string | null | undefined,
  apiKey: string | null | undefined
): string | null => {
  if (normalizeAuthMode(authMode) !== "single-user") {
    return null
  }

  const normalizedKey = String(apiKey || "").trim()
  return normalizedKey ? `key:${fnv1a36(normalizedKey)}` : "key:none"
}

export const buildChatSurfaceScopeKey = (
  input: ChatSurfaceScopeInput
): string => {
  const serverFingerprint = deriveServerFingerprint(input.serverUrl)
  const authScope = `auth:${normalizeAuthMode(input.authMode)}`
  const orgScope = normalizeOrgScope(input.orgId)
  const userScope = deriveScopedUserId({
    userId: input.userId,
    authMode: input.authMode,
    accessToken: input.accessToken ?? null
  })
  const singleUserApiKeyScope = deriveSingleUserApiKeyScope(
    input.authMode,
    input.apiKey ?? null
  )

  return singleUserApiKeyScope
    ? `${serverFingerprint}:${authScope}:${orgScope}:${userScope}:${singleUserApiKeyScope}`
    : `${serverFingerprint}:${authScope}:${orgScope}:${userScope}`
}

export const buildChatSurfaceScopeKeyFromConfig = (
  config: Pick<TldwConfig, "serverUrl" | "authMode" | "orgId" | "accessToken" | "apiKey"> | null | undefined,
  options?: {
    userId?: string | number | null
  }
): string =>
  buildChatSurfaceScopeKey({
    serverUrl: config?.serverUrl ?? null,
    authMode: config?.authMode ?? null,
    orgId: config?.orgId ?? null,
    userId: options?.userId ?? null,
    accessToken: config?.accessToken ?? null,
    apiKey: config?.apiKey ?? null
  })
