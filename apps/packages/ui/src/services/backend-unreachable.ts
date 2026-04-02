export type BackendUnreachableSource = "background" | "direct"

export type BackendUnreachableRecentRequestError = {
  method: string
  path: string
  status?: number
  error: string
  source: BackendUnreachableSource
  at: string
  ageMs: number
}

export type BackendUnreachableClassification = {
  kind: "backend_unreachable"
  title: string
  message: string
  rawMessage: string
  status?: number
  method?: string
  path?: string
  source?: BackendUnreachableSource
  recentRequestError?: BackendUnreachableRecentRequestError
  diagnostics: {
    matchedPattern: string
    status?: number
    recentRequestErrorAgeMs?: number
  }
}

export type BackendUnreachableOther = {
  kind: "other"
  rawMessage: string
  status?: number
  diagnostics: {
    reason: "abort_like" | "not_transport"
    matchedPattern?: string
  }
}

export type BackendUnreachableClassificationResult =
  | BackendUnreachableClassification
  | BackendUnreachableOther

export type BackendUnreachableClassifierOptions = {
  nowMs?: number
  recentRequestError?: unknown
  recentRequestErrorFreshnessMs?: number
}

type ErrorLike = {
  message?: unknown
  name?: unknown
  code?: unknown
  status?: unknown
  method?: unknown
  path?: unknown
  source?: unknown
}

export type BackendUnreachablePattern = {
  id: string
  pattern: RegExp
}

type RecentRequestErrorCandidate = {
  method?: unknown
  path?: unknown
  status?: unknown
  error?: unknown
  source?: unknown
  at?: unknown
}

export const BACKEND_UNREACHABLE_TRANSPORT_MESSAGE_PATTERNS: readonly BackendUnreachablePattern[] = [
  {
    id: "network_error_when_attempting_to_fetch_resource",
    pattern: /NetworkError when attempting to fetch resource\.?/i
  },
  {
    id: "failed_to_fetch_exact",
    pattern: /^(?:TypeError:\s*)?Failed to fetch\.?$/i
  }
]

export const BACKEND_UNREACHABLE_ABORT_MESSAGE_PATTERNS: readonly BackendUnreachablePattern[] = [
  {
    id: "abort_error_name",
    pattern: /^AbortError$/i
  },
  {
    id: "request_aborted_code",
    pattern: /^REQUEST_ABORTED$/i
  },
  {
    id: "operation_was_aborted",
    pattern: /^The operation was aborted\.?$/i
  }
]

export const DEFAULT_RECENT_REQUEST_ERROR_FRESHNESS_MS = 2 * 60_000

const normalizeString = (value: unknown): string =>
  typeof value === "string" ? value.trim() : ""

const getErrorLike = (error: unknown): ErrorLike =>
  typeof error === "object" && error !== null ? (error as ErrorLike) : {}

const getRawMessage = (error: unknown): string => {
  if (typeof error === "string") {
    return error.trim()
  }

  const candidate = normalizeString(getErrorLike(error).message)
  if (candidate) {
    return candidate
  }

  if (error instanceof Error && error.message) {
    return error.message.trim()
  }

  return normalizeString(String(error ?? ""))
}

const getRawName = (error: unknown): string => normalizeString(getErrorLike(error).name)

const getRawCode = (error: unknown): string => normalizeString(getErrorLike(error).code)

const parseStatus = (value: unknown): number | undefined => {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value
  }

  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : undefined
  }

  return undefined
}

const getStatus = (error: unknown): number | undefined =>
  parseStatus(getErrorLike(error).status)

const findMatchingPattern = (
  value: string,
  patterns: readonly BackendUnreachablePattern[]
): BackendUnreachablePattern | undefined => patterns.find(({ pattern }) => pattern.test(value))

const isAbortLike = (error: unknown, rawMessage: string): boolean => {
  const rawName = getRawName(error)
  const rawCode = getRawCode(error)

  return (
    Boolean(findMatchingPattern(rawMessage, BACKEND_UNREACHABLE_ABORT_MESSAGE_PATTERNS)) ||
    /^AbortError$/i.test(rawName) ||
    /^REQUEST_ABORTED$/i.test(rawCode)
  )
}

const parseRecentRequestError = (
  value: unknown,
  nowMs: number,
  freshnessLimitMs: number
): BackendUnreachableRecentRequestError | undefined => {
  if (typeof value !== "object" || value === null) {
    return undefined
  }

  const candidate = value as RecentRequestErrorCandidate
  const method = normalizeString(candidate.method)
  const path = normalizeString(candidate.path)
  const error = normalizeString(candidate.error)
  const source = normalizeString(candidate.source)
  const at = normalizeString(candidate.at)
  const status = parseStatus(candidate.status)

  if (!method || !path || !error || !at) {
    return undefined
  }

  if (source !== "background" && source !== "direct") {
    return undefined
  }

  const parsedAt = Date.parse(at)
  if (!Number.isFinite(parsedAt)) {
    return undefined
  }

  const ageMs = nowMs - parsedAt
  if (!Number.isFinite(ageMs) || ageMs < 0 || ageMs > freshnessLimitMs) {
    return undefined
  }

  return {
    method,
    path,
    status,
    error,
    source,
    at,
    ageMs
  }
}

const isTransportFailure = (
  error: unknown,
  rawMessage: string
): BackendUnreachablePattern | undefined => {
  const match = findMatchingPattern(rawMessage, BACKEND_UNREACHABLE_TRANSPORT_MESSAGE_PATTERNS)
  if (match) {
    return match
  }

  const status = getStatus(error)
  if (status === 0 && /\b(fetch|network)\b/i.test(rawMessage)) {
    return {
      id: "status_zero_transport_failure",
      pattern: /\b(fetch|network)\b/i
    }
  }

  return undefined
}

const readRequestContext = (
  error: unknown,
  recentRequestError?: BackendUnreachableRecentRequestError
): Pick<
  BackendUnreachableClassification,
  "method" | "path" | "source" | "status"
> => {
  const errorLike = getErrorLike(error)
  const method = normalizeString(errorLike.method) || recentRequestError?.method || ""
  const path = normalizeString(errorLike.path) || recentRequestError?.path || ""
  const sourceValue = normalizeString(errorLike.source)
  const source =
    sourceValue === "background" || sourceValue === "direct"
      ? (sourceValue as BackendUnreachableSource)
      : recentRequestError?.source
  const status = getStatus(error) ?? recentRequestError?.status

  return {
    ...(method ? { method } : {}),
    ...(path ? { path } : {}),
    ...(source ? { source } : {}),
    ...(typeof status === "number" ? { status } : {})
  }
}

export const classifyBackendUnreachableError = (
  error: unknown,
  options: BackendUnreachableClassifierOptions = {}
): BackendUnreachableClassificationResult => {
  const rawMessage = getRawMessage(error)
  const status = getStatus(error)
  const abortLike = isAbortLike(error, rawMessage)

  if (abortLike) {
    return {
      kind: "other",
      rawMessage,
      status,
      diagnostics: {
        reason: "abort_like"
      }
    }
  }

  if (!rawMessage) {
    return {
      kind: "other",
      rawMessage,
      status,
      diagnostics: {
        reason: "not_transport"
      }
    }
  }

  const transportMatch = isTransportFailure(error, rawMessage)
  if (!transportMatch) {
    return {
      kind: "other",
      rawMessage,
      status,
      diagnostics: {
        reason: "not_transport"
      }
    }
  }

  const nowMs = options.nowMs ?? Date.now()
  const freshnessLimitMs =
    options.recentRequestErrorFreshnessMs ?? DEFAULT_RECENT_REQUEST_ERROR_FRESHNESS_MS
  const recentRequestError = parseRecentRequestError(
    options.recentRequestError,
    nowMs,
    freshnessLimitMs
  )
  const requestContext = readRequestContext(error, recentRequestError)

  return {
    kind: "backend_unreachable",
    title: "Backend unreachable",
    message: "The browser could not reach the configured backend server.",
    rawMessage,
    ...requestContext,
    ...(recentRequestError ? { recentRequestError } : {}),
    diagnostics: {
      matchedPattern: transportMatch.id,
      ...(typeof status === "number" ? { status } : {}),
      ...(recentRequestError ? { recentRequestErrorAgeMs: recentRequestError.ageMs } : {})
    }
  }
}
