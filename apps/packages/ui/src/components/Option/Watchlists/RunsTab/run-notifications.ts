import type { WatchlistRun } from "@/types/watchlists"

type NotificationKind = "completed" | "failed"
export type RunFailureKind =
  | "auth"
  | "rate_limit"
  | "timeout"
  | "dns"
  | "tls"
  | "network"
  | "unknown"

interface RunNotificationDecision {
  kind: NotificationKind
  hint?: string | null
}

type Translator = (
  key: string,
  defaultValue?: string,
  options?: Record<string, unknown>
) => string

const ACTIVE_RUN_STATUSES = new Set(["pending", "running", "queued"])
const TERMINAL_RUN_STATUSES = new Set(["completed", "failed", "cancelled"])

const normalizeStatus = (status: string | null | undefined): string =>
  String(status || "").trim().toLowerCase()

const parseEpochMs = (value: string | null | undefined): number | null => {
  if (!value) return null
  const parsed = Date.parse(value)
  return Number.isFinite(parsed) ? parsed : null
}

const resolveHintCopy = (
  t: Translator | undefined,
  key: string,
  fallback: string
): string => {
  if (!t) return fallback
  try {
    const translated = t(key, fallback)
    if (!translated || translated === key) {
      return fallback
    }
    return translated
  } catch {
    return fallback
  }
}

export const getRunFailureHint = (
  errorMsg: string | null | undefined,
  t?: Translator
): string | null => {
  const kind = classifyRunFailure(errorMsg)
  if (kind === "auth") {
    return resolveHintCopy(
      t,
      "watchlists:notifications.failureHints.auth",
      "Source may require authentication. Verify credentials or access rules."
    )
  }
  if (kind === "rate_limit") {
    return resolveHintCopy(
      t,
      "watchlists:notifications.failureHints.rateLimit",
      "Source is rate-limiting requests. Reduce schedule frequency and retry."
    )
  }
  if (kind === "timeout") {
    return resolveHintCopy(
      t,
      "watchlists:notifications.failureHints.timeout",
      "The source request timed out. Retry, or lower concurrency for this source."
    )
  }
  if (kind === "dns") {
    return resolveHintCopy(
      t,
      "watchlists:notifications.failureHints.dns",
      "Source host could not be resolved. Verify the source URL and DNS availability."
    )
  }
  if (kind === "tls") {
    return resolveHintCopy(
      t,
      "watchlists:notifications.failureHints.tls",
      "TLS/SSL validation failed. Verify certificate chain or endpoint URL."
    )
  }
  if (kind === "network") {
    return resolveHintCopy(
      t,
      "watchlists:notifications.failureHints.network",
      "Source could not be reached. Check connectivity and endpoint availability."
    )
  }
  const normalized = String(errorMsg || "").toLowerCase()
  if (!normalized) {
    return resolveHintCopy(
      t,
      "watchlists:notifications.failureHints.unknownEmpty",
      "Open run details to inspect logs and retry."
    )
  }
  return resolveHintCopy(
    t,
    "watchlists:notifications.failureHints.unknown",
    "Open run details to inspect logs and adjust source or filter settings."
  )
}

export const classifyRunFailure = (errorMsg: string | null | undefined): RunFailureKind => {
  const normalized = String(errorMsg || "").toLowerCase()

  if (
    normalized.includes("403") ||
    normalized.includes("401") ||
    normalized.includes("forbidden") ||
    normalized.includes("unauthorized")
  ) {
    return "auth"
  }
  if (normalized.includes("429") || normalized.includes("rate limit")) {
    return "rate_limit"
  }
  if (normalized.includes("timeout") || normalized.includes("timed out")) {
    return "timeout"
  }
  if (normalized.includes("dns") || normalized.includes("name resolution")) {
    return "dns"
  }
  if (normalized.includes("ssl") || normalized.includes("certificate")) {
    return "tls"
  }
  if (
    normalized.includes("failed to fetch") ||
    normalized.includes("networkerror") ||
    normalized.includes("econnrefused") ||
    normalized.includes("unreachable")
  ) {
    return "network"
  }
  return "unknown"
}

export const resolveRunTransitionNotification = (
  previousStatus: string | null | undefined,
  run: Pick<WatchlistRun, "status" | "error_msg">,
  t?: Translator
): RunNotificationDecision | null => {
  const previous = normalizeStatus(previousStatus)
  const current = normalizeStatus(run.status)
  if (!previous || !current || previous === current) return null

  if (current === "completed" && ACTIVE_RUN_STATUSES.has(previous)) {
    return { kind: "completed" }
  }

  if (current === "failed" && (ACTIVE_RUN_STATUSES.has(previous) || previous === "completed")) {
    return {
      kind: "failed",
      hint: getRunFailureHint(run.error_msg, t)
    }
  }

  return null
}

export const shouldNotifyNewTerminalRun = (
  run: Pick<WatchlistRun, "status" | "finished_at">,
  sessionStartedAtMs: number
): boolean => {
  const current = normalizeStatus(run.status)
  if (!TERMINAL_RUN_STATUSES.has(current) || current === "cancelled") {
    return false
  }
  const finishedAtMs = parseEpochMs(run.finished_at)
  if (finishedAtMs == null) return false
  return finishedAtMs >= sessionStartedAtMs
}
