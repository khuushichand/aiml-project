import type { FlashcardsShortcutHintDensity } from "@/services/settings/ui-settings"
import { createSafeStorage } from "@/utils/safe-storage"

const storage = createSafeStorage({ area: "local" })

export const FLASHCARDS_SHORTCUT_HINT_TELEMETRY_STORAGE_KEY =
  "tldw:flashcards:shortcutHintTelemetry"
const MAX_RECENT_EVENTS = 200

export type FlashcardsShortcutHintSurface = "review" | "cards"
type VisibleHintDensity = Exclude<FlashcardsShortcutHintDensity, "hidden">

type EventDetails = Record<string, string | number | boolean | null>

export type FlashcardsShortcutHintTelemetryEvent =
  | {
      type: "flashcards_shortcut_hints_exposed"
      surface: FlashcardsShortcutHintSurface
      density: VisibleHintDensity
    }
  | {
      type: "flashcards_shortcut_hint_density_changed"
      surface: FlashcardsShortcutHintSurface
      from_density: FlashcardsShortcutHintDensity
      to_density: FlashcardsShortcutHintDensity
    }
  | {
      type: "flashcards_shortcut_hints_dismissed"
      surface: FlashcardsShortcutHintSurface
      from_density: VisibleHintDensity
    }

type FlashcardsShortcutHintRecentEvent = {
  type: FlashcardsShortcutHintTelemetryEvent["type"]
  at: number
  details: EventDetails
}

export type FlashcardsShortcutHintTelemetryState = {
  version: 1
  counters: Record<string, number>
  last_event_at: number | null
  last_density_by_surface: Record<
    FlashcardsShortcutHintSurface,
    FlashcardsShortcutHintDensity | null
  >
  exposures_by_surface_density: Record<string, number>
  dismissals_by_surface: Record<FlashcardsShortcutHintSurface, number>
  transitions_by_surface: Record<string, number>
  recent_events: FlashcardsShortcutHintRecentEvent[]
}

const DEFAULT_STATE: FlashcardsShortcutHintTelemetryState = {
  version: 1,
  counters: {},
  last_event_at: null,
  last_density_by_surface: {
    review: null,
    cards: null
  },
  exposures_by_surface_density: {},
  dismissals_by_surface: {
    review: 0,
    cards: 0
  },
  transitions_by_surface: {},
  recent_events: []
}

const toEventDetails = (
  event: FlashcardsShortcutHintTelemetryEvent
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

const incrementCounter = (counters: Record<string, number>, key: string) => {
  counters[key] = (counters[key] || 0) + 1
}

const readTelemetryState =
  async (): Promise<FlashcardsShortcutHintTelemetryState> => {
    const raw = await storage.get<FlashcardsShortcutHintTelemetryState | undefined>(
      FLASHCARDS_SHORTCUT_HINT_TELEMETRY_STORAGE_KEY
    )
    const state = raw && typeof raw === "object" ? raw : DEFAULT_STATE
    return {
      ...DEFAULT_STATE,
      ...state,
      counters: { ...DEFAULT_STATE.counters, ...(state.counters || {}) },
      last_density_by_surface: {
        ...DEFAULT_STATE.last_density_by_surface,
        ...(state.last_density_by_surface || {})
      },
      exposures_by_surface_density: {
        ...DEFAULT_STATE.exposures_by_surface_density,
        ...(state.exposures_by_surface_density || {})
      },
      dismissals_by_surface: {
        ...DEFAULT_STATE.dismissals_by_surface,
        ...(state.dismissals_by_surface || {})
      },
      transitions_by_surface: {
        ...DEFAULT_STATE.transitions_by_surface,
        ...(state.transitions_by_surface || {})
      },
      recent_events: Array.isArray(state.recent_events)
        ? state.recent_events.slice(-MAX_RECENT_EVENTS)
        : []
    }
  }

const writeTelemetryState = async (state: FlashcardsShortcutHintTelemetryState) => {
  await storage.set(FLASHCARDS_SHORTCUT_HINT_TELEMETRY_STORAGE_KEY, state)
}

export const trackFlashcardsShortcutHintTelemetry = async (
  event: FlashcardsShortcutHintTelemetryEvent
) => {
  try {
    const state = await readTelemetryState()
    const now = Date.now()
    state.last_event_at = now
    incrementCounter(state.counters, event.type)

    switch (event.type) {
      case "flashcards_shortcut_hints_exposed": {
        const exposureKey = `${event.surface}:${event.density}`
        state.exposures_by_surface_density[exposureKey] =
          (state.exposures_by_surface_density[exposureKey] || 0) + 1
        state.last_density_by_surface[event.surface] = event.density
        break
      }
      case "flashcards_shortcut_hint_density_changed": {
        const transitionKey = `${event.surface}:${event.from_density}->${event.to_density}`
        state.transitions_by_surface[transitionKey] =
          (state.transitions_by_surface[transitionKey] || 0) + 1
        state.last_density_by_surface[event.surface] = event.to_density
        break
      }
      case "flashcards_shortcut_hints_dismissed":
        state.dismissals_by_surface[event.surface] += 1
        state.last_density_by_surface[event.surface] = "hidden"
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
    console.warn("[flashcards-shortcut-hint-telemetry] Failed to record event", error)
  }
}

export const getFlashcardsShortcutHintTelemetryState =
  async (): Promise<FlashcardsShortcutHintTelemetryState> => readTelemetryState()

export const resetFlashcardsShortcutHintTelemetryState = async () => {
  await storage.set(
    FLASHCARDS_SHORTCUT_HINT_TELEMETRY_STORAGE_KEY,
    DEFAULT_STATE
  )
}

