import { createSafeStorage } from "@/utils/safe-storage"
import type { FlashcardsUiErrorCode } from "@/components/Flashcards/utils/error-taxonomy"

const storage = createSafeStorage({ area: "local" })

export const FLASHCARDS_ERROR_RECOVERY_TELEMETRY_STORAGE_KEY =
  "tldw:flashcards:errorRecoveryTelemetry"
const MAX_RECENT_EVENTS = 200

type FlashcardsRecoverySurface = "review" | "cards"

type EventDetails = Record<string, string | number | boolean | null>

export type FlashcardsErrorRecoveryTelemetryEvent =
  | {
      type: "flashcards_mutation_failed"
      surface: FlashcardsRecoverySurface
      operation: string
      error_code: FlashcardsUiErrorCode
      status?: number | null
      retriable: boolean
    }
  | {
      type: "flashcards_retry_requested"
      surface: FlashcardsRecoverySurface
      operation: string
      error_code: FlashcardsUiErrorCode
    }
  | {
      type: "flashcards_retry_succeeded"
      surface: FlashcardsRecoverySurface
      operation: string
      error_code: FlashcardsUiErrorCode
    }
  | {
      type: "flashcards_recovered_by_reload"
      surface: FlashcardsRecoverySurface
      operation: string
      error_code: FlashcardsUiErrorCode
    }

type FlashcardsErrorRecoveryRecentEvent = {
  type: FlashcardsErrorRecoveryTelemetryEvent["type"]
  at: number
  details: EventDetails
}

export type FlashcardsErrorRecoveryTelemetryState = {
  version: 1
  counters: Record<string, number>
  failures_by_code: Partial<Record<FlashcardsUiErrorCode, number>>
  retries_by_code: Partial<Record<FlashcardsUiErrorCode, number>>
  retry_success_by_code: Partial<Record<FlashcardsUiErrorCode, number>>
  reload_recovery_by_code: Partial<Record<FlashcardsUiErrorCode, number>>
  last_event_at: number | null
  recent_events: FlashcardsErrorRecoveryRecentEvent[]
}

const DEFAULT_STATE: FlashcardsErrorRecoveryTelemetryState = {
  version: 1,
  counters: {},
  failures_by_code: {},
  retries_by_code: {},
  retry_success_by_code: {},
  reload_recovery_by_code: {},
  last_event_at: null,
  recent_events: []
}

const incrementCounter = (counters: Record<string, number>, key: string) => {
  counters[key] = (counters[key] || 0) + 1
}

const incrementCodeCounter = (
  counters: Partial<Record<FlashcardsUiErrorCode, number>>,
  code: FlashcardsUiErrorCode
) => {
  counters[code] = (counters[code] || 0) + 1
}

const toEventDetails = (
  event: FlashcardsErrorRecoveryTelemetryEvent
): EventDetails => {
  const details: EventDetails = {}
  for (const [key, value] of Object.entries(event)) {
    if (key === "type") continue
    if (
      value == null ||
      typeof value === "string" ||
      typeof value === "number" ||
      typeof value === "boolean"
    ) {
      details[key] = value
    }
  }
  return details
}

const readTelemetryState =
  async (): Promise<FlashcardsErrorRecoveryTelemetryState> => {
    const raw = await storage.get<FlashcardsErrorRecoveryTelemetryState | undefined>(
      FLASHCARDS_ERROR_RECOVERY_TELEMETRY_STORAGE_KEY
    )
    const state = raw && typeof raw === "object" ? raw : DEFAULT_STATE
    return {
      ...DEFAULT_STATE,
      ...state,
      counters: { ...DEFAULT_STATE.counters, ...(state.counters || {}) },
      failures_by_code: {
        ...DEFAULT_STATE.failures_by_code,
        ...(state.failures_by_code || {})
      },
      retries_by_code: {
        ...DEFAULT_STATE.retries_by_code,
        ...(state.retries_by_code || {})
      },
      retry_success_by_code: {
        ...DEFAULT_STATE.retry_success_by_code,
        ...(state.retry_success_by_code || {})
      },
      reload_recovery_by_code: {
        ...DEFAULT_STATE.reload_recovery_by_code,
        ...(state.reload_recovery_by_code || {})
      },
      recent_events: Array.isArray(state.recent_events)
        ? state.recent_events.slice(-MAX_RECENT_EVENTS)
        : []
    }
  }

const writeTelemetryState = async (state: FlashcardsErrorRecoveryTelemetryState) => {
  await storage.set(FLASHCARDS_ERROR_RECOVERY_TELEMETRY_STORAGE_KEY, state)
}

export const trackFlashcardsErrorRecoveryTelemetry = async (
  event: FlashcardsErrorRecoveryTelemetryEvent
) => {
  try {
    const state = await readTelemetryState()
    const now = Date.now()
    state.last_event_at = now
    incrementCounter(state.counters, event.type)

    switch (event.type) {
      case "flashcards_mutation_failed":
        incrementCodeCounter(state.failures_by_code, event.error_code)
        break
      case "flashcards_retry_requested":
        incrementCodeCounter(state.retries_by_code, event.error_code)
        break
      case "flashcards_retry_succeeded":
        incrementCodeCounter(state.retry_success_by_code, event.error_code)
        break
      case "flashcards_recovered_by_reload":
        incrementCodeCounter(state.reload_recovery_by_code, event.error_code)
        break
      default:
        break
    }

    state.recent_events.push({
      type: event.type,
      at: now,
      details: toEventDetails(event)
    })
    if (state.recent_events.length > MAX_RECENT_EVENTS) {
      state.recent_events = state.recent_events.slice(-MAX_RECENT_EVENTS)
    }

    await writeTelemetryState(state)
  } catch (error) {
    console.warn("[flashcards-error-recovery-telemetry] Failed to record event", error)
  }
}

export const getFlashcardsErrorRecoveryTelemetryState =
  async (): Promise<FlashcardsErrorRecoveryTelemetryState> => readTelemetryState()

export const resetFlashcardsErrorRecoveryTelemetryState = async () => {
  await storage.set(FLASHCARDS_ERROR_RECOVERY_TELEMETRY_STORAGE_KEY, DEFAULT_STATE)
}
