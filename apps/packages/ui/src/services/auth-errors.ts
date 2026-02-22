import type { TFunction } from "i18next"

export type AuthErrorKind =
  | "invalidCredentials"
  | "forbidden"
  | "serverUnreachable"
  | "generic"

type ClassifiedError = {
  kind: AuthErrorKind
  status?: number
  raw: string
}

const extractStatusFromError = (error: unknown): number | undefined => {
  const explicit = (error as { status?: unknown } | null)?.status
  if (typeof explicit === "number" && Number.isFinite(explicit)) {
    return explicit
  }
  if (typeof explicit === "string") {
    const parsed = Number(explicit)
    if (Number.isFinite(parsed)) {
      return parsed
    }
  }

  const raw = String((error as { message?: unknown } | null)?.message || "")
  const match = raw.match(/\b(\d{3})\b/)
  if (!match) {
    return undefined
  }
  const parsed = Number(match[1])
  return Number.isFinite(parsed) ? parsed : undefined
}

const classifyAuthError = (error: unknown): ClassifiedError => {
  const raw = (error as any)?.message || ""
  const status = extractStatusFromError(error)

  const networkLike =
    typeof raw === "string" &&
    /network|timeout|failed to fetch|ECONNREFUSED|ENETUNREACH|ERR_CONNECTION/i.test(
      raw
    )

  if (status === 401) {
    return { kind: "invalidCredentials", status, raw }
  }
  if (status === 403) {
    return { kind: "forbidden", status, raw }
  }
  if (networkLike || /server not configured/i.test(raw)) {
    return { kind: "serverUnreachable", status, raw }
  }

  return { kind: "generic", status, raw }
}

export const isRecoverableAuthConfigError = (error: unknown): boolean => {
  const status = extractStatusFromError(error)
  if (status === 401 || status === 403) {
    return true
  }

  const raw = String((error as { message?: unknown } | null)?.message || "").toLowerCase()
  if (!raw) return false

  return (
    raw.includes("invalid api key") ||
    raw.includes("unauthorized") ||
    raw.includes("forbidden") ||
    raw.includes("server not configured")
  )
}

/**
 * Map multi-user login / auth failures to friendly, localized messages.
 *
 * surface = 'onboarding' | 'settings' to pick the appropriate namespace.
 */
export const mapMultiUserLoginErrorMessage = (
  t: TFunction,
  error: unknown,
  surface: "onboarding" | "settings"
): string => {
  const { kind, raw } = classifyAuthError(error)

  const baseKey =
    surface === "onboarding"
      ? "settings:onboarding.errors"
      : "settings:tldw.login"

  if (kind === "invalidCredentials") {
    return t(
      `${baseKey}.invalidCredentials`,
      surface === "onboarding"
        ? "Login failed. Check your username and password or confirm multi-user login is enabled on your tldw server."
        : "Login failed. Check your username/password or confirm multi-user auth is enabled on your tldw server."
    )
  }

  if (kind === "forbidden") {
    return t(
      `${baseKey}.forbidden`,
      surface === "onboarding"
        ? "Forbidden. Check that your user account has permission to log in."
        : "Forbidden. Check that this user has permission to log in."
    )
  }

  if (kind === "serverUnreachable") {
    return t(
      `${baseKey}.serverUnreachable`,
      "Couldn’t reach your tldw server. Check the server URL or open Health & diagnostics for more details."
    )
  }

  // generic fallback – include raw message for debugging but keep a friendly lead-in
  const friendly = t(
    `${baseKey}.generic`,
    "Login failed. See Health & diagnostics for server details."
  )
  if (raw && typeof raw === "string") {
    return `${friendly} (${raw})`
  }
  return friendly
}
