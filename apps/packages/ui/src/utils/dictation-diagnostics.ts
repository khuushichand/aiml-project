import type {
  DictationErrorClass,
  DictationModePreference,
  DictationResolvedMode,
  DictationToggleIntent
} from "@/hooks/useDictationStrategy"
import type { AudioSourceKind } from "@/audio"

export const DICTATION_DIAGNOSTICS_EVENT = "tldw:dictation:diagnostics"

export type DictationDiagnosticsSurface = "playground" | "sidepanel"
export type DictationDiagnosticsKind =
  | "toggle"
  | "server_error"
  | "server_success"

export type DictationDiagnosticsPayload = {
  version: 2
  at: string
  surface: DictationDiagnosticsSurface
  kind: DictationDiagnosticsKind
  requested_mode: DictationModePreference | "unknown"
  resolved_mode: DictationResolvedMode | "unknown"
  requested_source_kind: AudioSourceKind | "unknown"
  resolved_source_kind: AudioSourceKind | "unknown"
  speech_available: boolean
  speech_uses_server: boolean
  toggle_intent: DictationToggleIntent | null
  error_class: DictationErrorClass | null
  fallback_applied: boolean
  fallback_reason: DictationErrorClass | null
}

export type DictationDiagnosticsInput = {
  surface: DictationDiagnosticsSurface
  kind: DictationDiagnosticsKind
  requestedMode?: DictationModePreference | null
  resolvedMode?: DictationResolvedMode | null
  requestedSourceKind?: AudioSourceKind | null
  resolvedSourceKind?: AudioSourceKind | null
  speechAvailable?: boolean
  speechUsesServer?: boolean
  toggleIntent?: DictationToggleIntent | null
  errorClass?: DictationErrorClass | null
  fallbackApplied?: boolean
  fallbackReason?: DictationErrorClass | null
  at?: string | null
  version?: number
}

const REQUESTED_MODES: Set<DictationModePreference> = new Set([
  "auto",
  "server",
  "browser"
])

const RESOLVED_MODES: Set<DictationResolvedMode> = new Set([
  "server",
  "browser",
  "unavailable"
])

const SOURCE_KINDS: Set<AudioSourceKind> = new Set([
  "default_mic",
  "mic_device",
  "tab_audio",
  "system_audio"
])

const TOGGLE_INTENTS: Set<DictationToggleIntent> = new Set([
  "start_server",
  "stop_server",
  "start_browser",
  "stop_browser",
  "unavailable"
])

const ERROR_CLASSES: Set<DictationErrorClass> = new Set([
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

const normalizeText = (value: unknown): string => {
  if (typeof value === "string") return value.trim().toLowerCase()
  if (value == null) return ""
  try {
    return String(value).trim().toLowerCase()
  } catch {
    return ""
  }
}

const normalizeRequestedMode = (
  value: unknown
): DictationModePreference | "unknown" => {
  const normalized = normalizeText(value)
  if (REQUESTED_MODES.has(normalized as DictationModePreference)) {
    return normalized as DictationModePreference
  }
  return "unknown"
}

const normalizeResolvedMode = (
  value: unknown
): DictationResolvedMode | "unknown" => {
  const normalized = normalizeText(value)
  if (RESOLVED_MODES.has(normalized as DictationResolvedMode)) {
    return normalized as DictationResolvedMode
  }
  return "unknown"
}

const normalizeSourceKind = (value: unknown): AudioSourceKind | "unknown" => {
  const normalized = normalizeText(value)
  if (SOURCE_KINDS.has(normalized as AudioSourceKind)) {
    return normalized as AudioSourceKind
  }
  return "unknown"
}

const normalizeToggleIntent = (value: unknown): DictationToggleIntent | null => {
  const normalized = normalizeText(value)
  if (TOGGLE_INTENTS.has(normalized as DictationToggleIntent)) {
    return normalized as DictationToggleIntent
  }
  return null
}

const normalizeErrorClass = (value: unknown): DictationErrorClass | null => {
  const normalized = normalizeText(value)
  if (ERROR_CLASSES.has(normalized as DictationErrorClass)) {
    return normalized as DictationErrorClass
  }
  return null
}

const normalizeTimestamp = (value: unknown): string => {
  if (typeof value === "string") {
    const trimmed = value.trim()
    if (trimmed.length > 0) return trimmed
  }
  return new Date().toISOString()
}

export const sanitizeDictationDiagnosticsPayload = (
  input: DictationDiagnosticsInput
): DictationDiagnosticsPayload => ({
  version: 2,
  at: normalizeTimestamp(input.at),
  surface: input.surface === "sidepanel" ? "sidepanel" : "playground",
  kind:
    input.kind === "server_error" || input.kind === "server_success"
      ? input.kind
      : "toggle",
  requested_mode: normalizeRequestedMode(input.requestedMode),
  resolved_mode: normalizeResolvedMode(input.resolvedMode),
  requested_source_kind: normalizeSourceKind(input.requestedSourceKind),
  resolved_source_kind: normalizeSourceKind(input.resolvedSourceKind),
  speech_available: Boolean(input.speechAvailable),
  speech_uses_server: Boolean(input.speechUsesServer),
  toggle_intent: normalizeToggleIntent(input.toggleIntent),
  error_class: normalizeErrorClass(input.errorClass),
  fallback_applied: Boolean(input.fallbackApplied),
  fallback_reason: normalizeErrorClass(input.fallbackReason)
})

export const emitDictationDiagnostics = (
  input: DictationDiagnosticsInput
): DictationDiagnosticsPayload => {
  const payload = sanitizeDictationDiagnosticsPayload(input)
  if (typeof window === "undefined" || typeof window.dispatchEvent !== "function") {
    return payload
  }
  window.dispatchEvent(
    new CustomEvent<DictationDiagnosticsPayload>(DICTATION_DIAGNOSTICS_EVENT, {
      detail: payload
    })
  )
  return payload
}
