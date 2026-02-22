import type { ConversationShareLinkSummary } from "@/services/tldw/TldwApiClient"

const parseTimestamp = (value?: string | null): number | null => {
  if (!value || typeof value !== "string") return null
  const parsed = Date.parse(value)
  return Number.isNaN(parsed) ? null : parsed
}

export const isShareLinkExpired = (
  link: Pick<ConversationShareLinkSummary, "expires_at">,
  now = Date.now()
): boolean => {
  const expiresAt = parseTimestamp(link.expires_at)
  if (expiresAt == null) return true
  return expiresAt <= now
}

export const isShareLinkRevoked = (
  link: Pick<ConversationShareLinkSummary, "revoked_at">,
  now = Date.now()
): boolean => {
  if (!link.revoked_at) return false
  const revokedAt = parseTimestamp(link.revoked_at)
  if (revokedAt == null) return true
  return revokedAt <= now
}

export const isShareLinkActive = (
  link: Pick<ConversationShareLinkSummary, "expires_at" | "revoked_at">,
  now = Date.now()
): boolean => !isShareLinkRevoked(link, now) && !isShareLinkExpired(link, now)

export const getActiveShareLinkCount = (
  links: ConversationShareLinkSummary[],
  now = Date.now()
): number => links.filter((link) => isShareLinkActive(link, now)).length

export const sortShareLinksByCreatedDesc = (
  links: ConversationShareLinkSummary[]
): ConversationShareLinkSummary[] =>
  [...links].sort((a, b) => {
    const aTime = parseTimestamp(a.created_at) || 0
    const bTime = parseTimestamp(b.created_at) || 0
    return bTime - aTime
  })

export const buildConversationShareUrl = (
  origin: string,
  link: Pick<ConversationShareLinkSummary, "share_path" | "token"> | null | undefined
): string | null => {
  if (!link) return null
  if (typeof link.share_path === "string" && link.share_path.trim().length > 0) {
    return `${origin}${link.share_path.trim()}`
  }
  if (typeof link.token === "string" && link.token.trim().length > 0) {
    return `${origin}/knowledge/shared/${encodeURIComponent(link.token.trim())}`
  }
  return null
}
