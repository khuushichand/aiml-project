import type { WatchlistRun } from "@/types/watchlists"

type NotificationKind = "completed" | "failed"

interface RunNotificationDecision {
  kind: NotificationKind
  hint?: string | null
}

const ACTIVE_RUN_STATUSES = new Set(["pending", "running", "queued"])
const TERMINAL_RUN_STATUSES = new Set(["completed", "failed", "cancelled"])

const normalizeStatus = (status: string | null | undefined): string =>
  String(status || "").trim().toLowerCase()

const parseEpochMs = (value: string | null | undefined): number | null => {
  if (!value) return null
  const parsed = Date.parse(value)
  return Number.isFinite(parsed) ? parsed : null
}

export const getRunFailureHint = (errorMsg: string | null | undefined): string | null => {
  const normalized = String(errorMsg || "").toLowerCase()
  if (!normalized) {
    return "Open run details to inspect logs and retry."
  }
  if (
    normalized.includes("403") ||
    normalized.includes("401") ||
    normalized.includes("forbidden") ||
    normalized.includes("unauthorized")
  ) {
    return "Source may require authentication. Verify credentials or access rules."
  }
  if (normalized.includes("429") || normalized.includes("rate limit")) {
    return "Source is rate-limiting requests. Reduce schedule frequency and retry."
  }
  if (normalized.includes("timeout") || normalized.includes("timed out")) {
    return "The source request timed out. Retry, or lower concurrency for this source."
  }
  if (normalized.includes("dns") || normalized.includes("name resolution")) {
    return "Source host could not be resolved. Verify the source URL and DNS availability."
  }
  if (normalized.includes("ssl") || normalized.includes("certificate")) {
    return "TLS/SSL validation failed. Verify certificate chain or endpoint URL."
  }
  return "Open run details to inspect logs and adjust source or filter settings."
}

export const resolveRunTransitionNotification = (
  previousStatus: string | null | undefined,
  run: Pick<WatchlistRun, "status" | "error_msg">
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
      hint: getRunFailureHint(run.error_msg)
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
