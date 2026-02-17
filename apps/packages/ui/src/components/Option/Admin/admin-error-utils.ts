export type AdminGuardState = "forbidden" | "notFound" | null

const ADMIN_NOT_FOUND_CODES = new Set(["404", "405", "410", "501", "503"])

const normalizeErrorMessage = (error: unknown): string => {
  if (typeof error === "string") return error
  if (error && typeof error === "object" && "message" in error) {
    return String((error as { message?: unknown }).message ?? "")
  }
  return ""
}

export const deriveAdminGuardFromError = (error: unknown): AdminGuardState => {
  const rawMessage = normalizeErrorMessage(error)
  const statusMatch = rawMessage.match(/Request failed:\s*(\d{3})/i)
  const statusCode = statusMatch?.[1]

  if (statusCode === "403") {
    return "forbidden"
  }
  if (statusCode && ADMIN_NOT_FOUND_CODES.has(statusCode)) {
    return "notFound"
  }
  return null
}

export const sanitizeAdminErrorMessage = (
  error: unknown,
  fallbackMessage: string
): string => {
  const rawMessage = normalizeErrorMessage(error)
  if (!rawMessage.trim()) return fallbackMessage

  const firstLine = rawMessage
    .split("\n")
    .map((line) => line.trim())
    .find((line) => line.length > 0)

  let cleaned = (firstLine || rawMessage).replace(/^Error:\s*/i, "")

  // Avoid surfacing raw endpoint paths in user-facing admin errors.
  cleaned = cleaned.replace(
    /\b(GET|POST|PUT|PATCH|DELETE)\s+\/api\/v1\/[^\s)]+/gi,
    "$1 [admin-endpoint]"
  )
  cleaned = cleaned.replace(/\b\/api\/v1\/[^\s)]+/gi, "[admin-endpoint]")

  // Redact filesystem paths from backend traces/messages.
  cleaned = cleaned.replace(
    /\/(?:Users|home|var|etc|opt|tmp|private|srv)\/[^\s)]+/g,
    "[redacted-path]"
  )
  cleaned = cleaned.replace(
    /[A-Za-z]:\\(?:[^\\\s]+\\)+[^\\\s)]+/g,
    "[redacted-path]"
  )

  if (cleaned.length > 220) {
    cleaned = `${cleaned.slice(0, 217)}...`
  }

  return cleaned || fallbackMessage
}

