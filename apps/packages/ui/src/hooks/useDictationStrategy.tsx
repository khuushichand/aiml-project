import React from "react"

export type DictationModePreference = "auto" | "server" | "browser"
export type DictationResolvedMode = "server" | "browser" | "unavailable"
export type DictationToggleIntent =
  | "start_server"
  | "stop_server"
  | "start_browser"
  | "stop_browser"
  | "unavailable"

export type DictationErrorClass =
  | "permission_denied"
  | "unsupported_api"
  | "auth_error"
  | "quota_error"
  | "provider_unavailable"
  | "model_unavailable"
  | "transient_failure"
  | "empty_transcript"
  | "unknown_error"

const VALID_DICTATION_MODE_PREFERENCES: Set<DictationModePreference> = new Set(
  ["auto", "server", "browser"]
)

const VALID_DICTATION_ERROR_CLASSES: Set<DictationErrorClass> = new Set([
  "permission_denied",
  "unsupported_api",
  "auth_error",
  "quota_error",
  "provider_unavailable",
  "model_unavailable",
  "transient_failure",
  "empty_transcript",
  "unknown_error"
])

const AUTO_FALLBACK_ERROR_CLASSES: Set<DictationErrorClass> = new Set([
  "unsupported_api",
  "provider_unavailable",
  "model_unavailable",
  "transient_failure"
])

const STATUS_HINT_TO_ERROR_CLASS: Record<string, DictationErrorClass> = {
  permission_denied: "permission_denied",
  mic_permission_denied: "permission_denied",
  unsupported_api: "unsupported_api",
  unsupported_browser: "unsupported_api",
  auth_error: "auth_error",
  unauthorized: "auth_error",
  forbidden: "auth_error",
  quota_error: "quota_error",
  quota_exceeded: "quota_error",
  rate_limited: "quota_error",
  provider_unavailable: "provider_unavailable",
  model_unavailable: "model_unavailable",
  model_downloading: "model_unavailable",
  transient_failure: "transient_failure",
  network_error: "transient_failure",
  timeout: "transient_failure",
  empty_transcript: "empty_transcript"
}

const asText = (value: unknown): string => {
  if (typeof value === "string") return value
  if (value == null) return ""
  try {
    return String(value)
  } catch {
    return ""
  }
}

const asLowerText = (value: unknown): string => asText(value).trim().toLowerCase()

const getStatusCode = (error: unknown): number | null => {
  const candidate = error as
    | {
        status?: unknown
        response?: { status?: unknown } | null
      }
    | null
    | undefined
  const rawStatus = candidate?.status ?? candidate?.response?.status
  const status =
    typeof rawStatus === "number"
      ? rawStatus
      : typeof rawStatus === "string"
        ? Number(rawStatus)
        : Number.NaN
  if (!Number.isFinite(status)) return null
  return Number(status)
}

const coerceErrorClass = (value: unknown): DictationErrorClass | null => {
  const normalized = asLowerText(value)
  if (VALID_DICTATION_ERROR_CLASSES.has(normalized as DictationErrorClass)) {
    return normalized as DictationErrorClass
  }
  return null
}

const readDetailPayload = (error: unknown): Record<string, unknown> | null => {
  const candidate = error as
    | {
        details?: unknown
        detail?: unknown
        response?: { data?: unknown } | null
      }
    | null
    | undefined
  const details = candidate?.details
  if (details && typeof details === "object") {
    return details as Record<string, unknown>
  }
  const detail = candidate?.detail
  if (detail && typeof detail === "object") {
    return detail as Record<string, unknown>
  }
  const responseData = candidate?.response?.data
  if (responseData && typeof responseData === "object") {
    return responseData as Record<string, unknown>
  }
  return null
}

const readStatusHint = (payload: Record<string, unknown> | null): string => {
  if (!payload) return ""
  const directKeys = ["status", "error_code", "error_type", "code"]
  for (const key of directKeys) {
    const value = asLowerText(payload[key])
    if (value) return value
  }
  const nested = payload.detail
  if (nested && typeof nested === "object") {
    return readStatusHint(nested as Record<string, unknown>)
  }
  return ""
}

const readErrorMessage = (
  error: unknown,
  payload: Record<string, unknown> | null
): string => {
  const parts: string[] = []
  const keys = ["message", "error", "detail", "details", "status"]
  if (payload) {
    for (const key of keys) {
      const value = payload[key]
      if (typeof value === "string") {
        const normalized = value.trim()
        if (normalized) parts.push(normalized)
      }
    }
  }
  const message = asText((error as { message?: unknown } | null)?.message).trim()
  if (message) parts.push(message)
  return parts.join(" ").toLowerCase()
}

const classifyFromStatusHint = (
  statusHint: string
): DictationErrorClass | null => {
  if (!statusHint) return null
  const mapped = STATUS_HINT_TO_ERROR_CLASS[statusHint]
  if (mapped) return mapped
  if (statusHint.includes("provider_unavailable")) return "provider_unavailable"
  if (statusHint.includes("model_downloading")) return "model_unavailable"
  if (statusHint.includes("model_unavailable")) return "model_unavailable"
  if (statusHint.includes("quota") || statusHint.includes("rate_limit")) return "quota_error"
  if (statusHint.includes("permission")) return "permission_denied"
  if (statusHint.includes("unsupported")) return "unsupported_api"
  if (
    statusHint.includes("auth") ||
    statusHint.includes("unauthorized") ||
    statusHint.includes("forbidden")
  ) {
    return "auth_error"
  }
  if (statusHint.includes("timeout") || statusHint.includes("network")) {
    return "transient_failure"
  }
  return null
}

export const classifyDictationError = (error: unknown): DictationErrorClass => {
  const payload = readDetailPayload(error)
  const explicitClass = coerceErrorClass(payload?.dictation_error_class)
  if (explicitClass) return explicitClass

  const nestedClass =
    payload?.detail && typeof payload.detail === "object"
      ? coerceErrorClass((payload.detail as Record<string, unknown>).dictation_error_class)
      : null
  if (nestedClass) return nestedClass

  const statusHint = readStatusHint(payload)
  const statusHintClass = classifyFromStatusHint(statusHint)
  if (statusHintClass) return statusHintClass

  const statusCode = getStatusCode(error)
  if (statusCode === 401 || statusCode === 403) return "auth_error"
  if (statusCode === 402 || statusCode === 429) return "quota_error"

  const message = readErrorMessage(error, payload)
  if (
    message.includes("permission denied") ||
    message.includes("microphone permission") ||
    message.includes("notallowederror")
  ) {
    return "permission_denied"
  }
  if (
    message.includes("unsupported api") ||
    message.includes("speechrecognition") ||
    message.includes("not supported")
  ) {
    return "unsupported_api"
  }
  if (
    message.includes("unauthorized") ||
    message.includes("forbidden") ||
    message.includes("invalid api key") ||
    message.includes("authentication")
  ) {
    return "auth_error"
  }
  if (
    message.includes("quota") ||
    message.includes("rate limit") ||
    message.includes("too many requests") ||
    message.includes("payment required")
  ) {
    return "quota_error"
  }
  if (message.includes("provider unavailable")) return "provider_unavailable"
  if (
    message.includes("model downloading") ||
    message.includes("model unavailable") ||
    message.includes("not available locally")
  ) {
    return "model_unavailable"
  }
  if (
    message.includes("empty transcript") ||
    message.includes("did not return any text") ||
    message.includes("no transcript")
  ) {
    return "empty_transcript"
  }

  if (
    statusCode === 408 ||
    statusCode === 500 ||
    statusCode === 502 ||
    statusCode === 503 ||
    statusCode === 504
  ) {
    return "transient_failure"
  }
  if (
    message.includes("timeout") ||
    message.includes("timed out") ||
    message.includes("network error") ||
    message.includes("connection")
  ) {
    return "transient_failure"
  }
  return "unknown_error"
}

export const dictationErrorAllowsAutoFallback = (
  errorClass: DictationErrorClass
): boolean => AUTO_FALLBACK_ERROR_CLASSES.has(errorClass)

export const resolveRequestedDictationMode = (
  modeOverride: DictationModePreference | null | undefined,
  autoFallbackEnabled: boolean
): DictationModePreference => {
  const normalizedOverride = asLowerText(modeOverride)
  if (
    normalizedOverride &&
    VALID_DICTATION_MODE_PREFERENCES.has(
      normalizedOverride as DictationModePreference
    )
  ) {
    return normalizedOverride as DictationModePreference
  }
  return autoFallbackEnabled ? "auto" : "server"
}

type ResolveDictationModeInput = {
  requestedMode: DictationModePreference
  canUseServerStt: boolean
  browserSupportsSpeechRecognition: boolean
  forceAutoBrowserFallback?: boolean
}

export const resolveDictationMode = ({
  requestedMode,
  canUseServerStt,
  browserSupportsSpeechRecognition,
  forceAutoBrowserFallback = false
}: ResolveDictationModeInput): DictationResolvedMode => {
  if (requestedMode === "server") {
    return canUseServerStt ? "server" : "unavailable"
  }
  if (requestedMode === "browser") {
    return browserSupportsSpeechRecognition ? "browser" : "unavailable"
  }
  if (forceAutoBrowserFallback && browserSupportsSpeechRecognition) {
    return "browser"
  }
  if (canUseServerStt) return "server"
  if (browserSupportsSpeechRecognition) return "browser"
  return "unavailable"
}

export type UseDictationStrategyOptions = {
  canUseServerStt: boolean
  browserSupportsSpeechRecognition: boolean
  isServerDictating: boolean
  isBrowserDictating: boolean
  modeOverride?: DictationModePreference | null
  autoFallbackEnabled: boolean
}

export type UseDictationStrategyResult = {
  requestedMode: DictationModePreference
  resolvedMode: DictationResolvedMode
  speechAvailable: boolean
  speechUsesServer: boolean
  isDictating: boolean
  toggleIntent: DictationToggleIntent
  autoFallbackActive: boolean
  autoFallbackErrorClass: DictationErrorClass | null
  recordServerError: (error: unknown) => DictationServerErrorTransition
  recordServerSuccess: () => void
  clearAutoFallback: () => void
}

export type DictationServerErrorTransition = {
  errorClass: DictationErrorClass
  appliedFallback: boolean
  requestedMode: DictationModePreference
  resolvedModeBeforeError: DictationResolvedMode
  speechAvailableBeforeError: boolean
  speechUsesServerBeforeError: boolean
  browserSupportsSpeechRecognition: boolean
  autoFallbackEnabled: boolean
}

export const useDictationStrategy = (
  options: UseDictationStrategyOptions
): UseDictationStrategyResult => {
  const {
    canUseServerStt,
    browserSupportsSpeechRecognition,
    isServerDictating,
    isBrowserDictating,
    modeOverride = null,
    autoFallbackEnabled
  } = options

  const requestedMode = React.useMemo(
    () => resolveRequestedDictationMode(modeOverride, autoFallbackEnabled),
    [autoFallbackEnabled, modeOverride]
  )

  const [autoFallbackErrorClass, setAutoFallbackErrorClass] =
    React.useState<DictationErrorClass | null>(null)

  React.useEffect(() => {
    if (requestedMode !== "auto" || !autoFallbackEnabled) {
      setAutoFallbackErrorClass(null)
    }
  }, [autoFallbackEnabled, requestedMode])

  const autoFallbackActive =
    requestedMode === "auto" &&
    autoFallbackEnabled &&
    autoFallbackErrorClass !== null &&
    browserSupportsSpeechRecognition

  const resolvedMode = React.useMemo(
    () =>
      resolveDictationMode({
        requestedMode,
        canUseServerStt,
        browserSupportsSpeechRecognition,
        forceAutoBrowserFallback: autoFallbackActive
      }),
    [
      autoFallbackActive,
      browserSupportsSpeechRecognition,
      canUseServerStt,
      requestedMode
    ]
  )

  const speechAvailable = resolvedMode !== "unavailable"
  const speechUsesServer = resolvedMode === "server"
  const isDictating =
    resolvedMode === "server"
      ? isServerDictating
      : resolvedMode === "browser"
        ? isBrowserDictating
        : false

  const toggleIntent: DictationToggleIntent =
    resolvedMode === "unavailable"
      ? "unavailable"
      : resolvedMode === "server"
        ? isServerDictating
          ? "stop_server"
          : "start_server"
        : isBrowserDictating
          ? "stop_browser"
          : "start_browser"

  const clearAutoFallback = React.useCallback(() => {
    setAutoFallbackErrorClass(null)
  }, [])

  const recordServerSuccess = React.useCallback(() => {
    setAutoFallbackErrorClass(null)
  }, [])

  const recordServerError = React.useCallback(
    (error: unknown) => {
      const errorClass = classifyDictationError(error)
      const allowFallback =
        requestedMode === "auto" &&
        autoFallbackEnabled &&
        browserSupportsSpeechRecognition &&
        dictationErrorAllowsAutoFallback(errorClass)
      if (allowFallback) {
        setAutoFallbackErrorClass(errorClass)
      }
      return {
        errorClass,
        appliedFallback: allowFallback,
        requestedMode,
        resolvedModeBeforeError: resolvedMode,
        speechAvailableBeforeError: speechAvailable,
        speechUsesServerBeforeError: speechUsesServer,
        browserSupportsSpeechRecognition,
        autoFallbackEnabled
      }
    },
    [
      autoFallbackEnabled,
      browserSupportsSpeechRecognition,
      requestedMode,
      resolvedMode,
      speechAvailable,
      speechUsesServer
    ]
  )

  return {
    requestedMode,
    resolvedMode,
    speechAvailable,
    speechUsesServer,
    isDictating,
    toggleIntent,
    autoFallbackActive,
    autoFallbackErrorClass,
    recordServerError,
    recordServerSuccess,
    clearAutoFallback
  }
}
