import { createSafeStorage } from "@/utils/safe-storage"

const storage = createSafeStorage({ area: "local" })

export const WATCHLISTS_PREVENTION_TELEMETRY_STORAGE_KEY =
  "tldw:watchlists:preventionTelemetry"
const MAX_RECENT_EVENTS = 200

export type WatchlistsPreventionSurface =
  | "job_form"
  | "schedule_picker"
  | "groups_tree"

export type WatchlistsPreventionRule =
  | "scope_required"
  | "schedule_too_frequent"
  | "invalid_email_recipients"
  | "group_cycle_parent"

type EventDetails = Record<string, string | number | boolean | null>

export type WatchlistsPreventionTelemetryEvent = {
  type: "watchlists_validation_blocked"
  surface: WatchlistsPreventionSurface
  rule: WatchlistsPreventionRule
  remediation: string
  count?: number
  minutes?: number
}

type WatchlistsPreventionRecentEvent = {
  type: WatchlistsPreventionTelemetryEvent["type"]
  at: number
  details: EventDetails
}

export type WatchlistsPreventionTelemetryState = {
  version: 1
  counters: Record<string, number>
  blocked_by_rule: Record<WatchlistsPreventionRule, number>
  blocked_by_surface: Record<WatchlistsPreventionSurface, number>
  last_event_at: number | null
  recent_events: WatchlistsPreventionRecentEvent[]
}

const DEFAULT_STATE: WatchlistsPreventionTelemetryState = {
  version: 1,
  counters: {},
  blocked_by_rule: {
    scope_required: 0,
    schedule_too_frequent: 0,
    invalid_email_recipients: 0,
    group_cycle_parent: 0
  },
  blocked_by_surface: {
    job_form: 0,
    schedule_picker: 0,
    groups_tree: 0
  },
  last_event_at: null,
  recent_events: []
}

const incrementCounter = (counters: Record<string, number>, key: string) => {
  counters[key] = (counters[key] || 0) + 1
}

const toEventDetails = (
  event: WatchlistsPreventionTelemetryEvent
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
  async (): Promise<WatchlistsPreventionTelemetryState> => {
    const raw = await storage.get<WatchlistsPreventionTelemetryState | undefined>(
      WATCHLISTS_PREVENTION_TELEMETRY_STORAGE_KEY
    )
    const state = raw && typeof raw === "object" ? raw : DEFAULT_STATE
    return {
      ...DEFAULT_STATE,
      ...state,
      counters: { ...DEFAULT_STATE.counters, ...(state.counters || {}) },
      blocked_by_rule: {
        ...DEFAULT_STATE.blocked_by_rule,
        ...(state.blocked_by_rule || {})
      },
      blocked_by_surface: {
        ...DEFAULT_STATE.blocked_by_surface,
        ...(state.blocked_by_surface || {})
      },
      recent_events: Array.isArray(state.recent_events)
        ? state.recent_events.slice(-MAX_RECENT_EVENTS)
        : []
    }
  }

const writeTelemetryState = async (state: WatchlistsPreventionTelemetryState) => {
  await storage.set(WATCHLISTS_PREVENTION_TELEMETRY_STORAGE_KEY, state)
}

export const trackWatchlistsPreventionTelemetry = async (
  event: WatchlistsPreventionTelemetryEvent
) => {
  try {
    const state = await readTelemetryState()
    const now = Date.now()
    state.last_event_at = now
    incrementCounter(state.counters, event.type)
    state.blocked_by_rule[event.rule] += 1
    state.blocked_by_surface[event.surface] += 1
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
    console.warn("[watchlists-prevention-telemetry] Failed to record event", error)
  }
}

export const getWatchlistsPreventionTelemetryState =
  async (): Promise<WatchlistsPreventionTelemetryState> => readTelemetryState()

export const resetWatchlistsPreventionTelemetryState = async () => {
  await storage.set(WATCHLISTS_PREVENTION_TELEMETRY_STORAGE_KEY, DEFAULT_STATE)
}

