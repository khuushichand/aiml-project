import { formatErrorMessage } from "@/utils/format-error-message"

type ErrorSeverity = "warning" | "error"
type ErrorKind =
  | "network"
  | "timeout"
  | "auth"
  | "rate_limit"
  | "not_found"
  | "server"
  | "unknown"

type Translator = (
  key: string,
  defaultValue?: string,
  options?: Record<string, unknown>
) => string

export interface WatchlistsMappedError {
  kind: ErrorKind
  severity: ErrorSeverity
  status: number | null
  title: string
  description: string
  rawMessage: string
}

interface MapWatchlistsErrorOptions {
  context: string
  fallbackMessage?: string
  operationLabel?: string
  t: Translator
}

const asRecord = (value: unknown): Record<string, unknown> | null => {
  if (typeof value === "object" && value !== null && !Array.isArray(value)) {
    return value as Record<string, unknown>
  }
  return null
}

const toFiniteNumber = (value: unknown): number | null => {
  const parsed =
    typeof value === "number"
      ? value
      : typeof value === "string"
        ? Number(value)
        : Number.NaN
  return Number.isFinite(parsed) ? parsed : null
}

const extractStatus = (error: unknown): number | null => {
  const direct = asRecord(error)
  if (!direct) return null

  const directStatus = toFiniteNumber(direct.status)
  if (directStatus != null) return directStatus

  const response = asRecord(direct.response)
  if (response) {
    const responseStatus = toFiniteNumber(response.status)
    if (responseStatus != null) return responseStatus
  }

  const details = asRecord(direct.details)
  if (details) {
    const detailsStatus = toFiniteNumber(details.status)
    if (detailsStatus != null) return detailsStatus
  }

  return null
}

const classifyError = (status: number | null, rawMessage: string): ErrorKind => {
  const normalized = rawMessage.toLowerCase()

  if (
    status === 401 ||
    status === 403 ||
    normalized.includes("forbidden") ||
    normalized.includes("unauthorized") ||
    normalized.includes("permission denied")
  ) {
    return "auth"
  }

  if (
    status === 429 ||
    normalized.includes("rate limit") ||
    normalized.includes("too many requests")
  ) {
    return "rate_limit"
  }

  if (status === 404) {
    return "not_found"
  }

  if (status != null && status >= 500) {
    return "server"
  }

  if (
    normalized.includes("timeout") ||
    normalized.includes("timed out") ||
    normalized.includes("aborterror")
  ) {
    return "timeout"
  }

  if (
    normalized.includes("failed to fetch") ||
    normalized.includes("networkerror") ||
    normalized.includes("network request failed") ||
    normalized.includes("econnrefused") ||
    normalized.includes("offline") ||
    normalized.includes("unreachable") ||
    normalized.includes("cors")
  ) {
    return "network"
  }

  return "unknown"
}

const toSeverity = (kind: ErrorKind): ErrorSeverity => {
  if (kind === "auth" || kind === "rate_limit" || kind === "not_found") {
    return "warning"
  }
  return "error"
}

const isGeneric = (value: string): boolean => {
  const normalized = value.trim().toLowerCase()
  if (!normalized) return true
  return (
    normalized === "request failed" ||
    normalized === "failed to load" ||
    normalized === "unknown error"
  )
}

const getNextStep = (
  kind: ErrorKind,
  t: Translator,
  context: string
): string => {
  if (kind === "auth") {
    return t(
      "watchlists:errors.next.auth",
      "Verify your login/API key permissions for {{context}}, then retry.",
      { context }
    )
  }
  if (kind === "rate_limit") {
    return t(
      "watchlists:errors.next.rateLimit",
      "Reduce monitor frequency or wait briefly before retrying.",
      { context }
    )
  }
  if (kind === "timeout") {
    return t(
      "watchlists:errors.next.timeout",
      "Retry now. If this continues, reduce scope or schedule intensity.",
      { context }
    )
  }
  if (kind === "network") {
    return t(
      "watchlists:errors.next.network",
      "Check server connection and try again.",
      { context }
    )
  }
  if (kind === "server") {
    return t(
      "watchlists:errors.next.server",
      "Retry in a moment. If this keeps failing, check server logs.",
      { context }
    )
  }
  if (kind === "not_found") {
    return t(
      "watchlists:errors.next.notFound",
      "Refresh the list and confirm the requested records still exist.",
      { context }
    )
  }
  return t(
    "watchlists:errors.next.generic",
    "Retry the request. If the problem continues, review server diagnostics.",
    { context }
  )
}

export const mapWatchlistsError = (
  error: unknown,
  options: MapWatchlistsErrorOptions
): WatchlistsMappedError => {
  const {
    context,
    fallbackMessage = "Request failed",
    operationLabel,
    t
  } = options
  const status = extractStatus(error)
  const rawMessage = formatErrorMessage(error, fallbackMessage)
  const kind = classifyError(status, rawMessage)
  const severity = toSeverity(kind)
  const operation = operationLabel || t("watchlists:errors.operation.load", "load")
  const title = t("watchlists:errors.title", "Could not {{operation}} {{context}}.", {
    operation,
    context
  })
  const nextStep = getNextStep(kind, t, context)
  const details = isGeneric(rawMessage)
    ? ""
    : t("watchlists:errors.details", "Details: {{message}}", {
        message: rawMessage
      })
  const description = details ? `${nextStep} ${details}` : nextStep

  return {
    kind,
    severity,
    status,
    title,
    description,
    rawMessage
  }
}

