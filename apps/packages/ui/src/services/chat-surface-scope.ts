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

  return `${serverFingerprint}:${authScope}:${orgScope}:${userScope}`
}

export const buildChatSurfaceScopeKeyFromConfig = (
  config: Pick<TldwConfig, "serverUrl" | "authMode" | "orgId" | "accessToken"> | null | undefined,
  options?: {
    userId?: string | number | null
  }
): string =>
  buildChatSurfaceScopeKey({
    serverUrl: config?.serverUrl ?? null,
    authMode: config?.authMode ?? null,
    orgId: config?.orgId ?? null,
    userId: options?.userId ?? null,
    accessToken: config?.accessToken ?? null
  })
