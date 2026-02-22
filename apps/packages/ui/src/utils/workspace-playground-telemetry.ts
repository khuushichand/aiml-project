import { createSafeStorage } from "@/utils/safe-storage"

const storage = createSafeStorage({ area: "local" })

export const WORKSPACE_PLAYGROUND_TELEMETRY_STORAGE_KEY =
  "tldw:workspace:playground:telemetry"
const MAX_RECENT_EVENTS = 200

export type WorkspacePlaygroundTelemetryEventType =
  | "status_viewed"
  | "citation_provenance_opened"
  | "token_cost_rendered"
  | "diagnostics_toggled"
  | "quota_warning_seen"
  | "conflict_modal_opened"
  | "undo_triggered"
  | "operation_cancelled"
  | "artifact_rehydrated_failed"
  | "source_status_polled"
  | "source_status_ready"
  | "connectivity_state_changed"
  | "confusion_retry_burst"
  | "confusion_refresh_loop"
  | "confusion_duplicate_submission"

type EventDetails = Record<string, string | number | boolean | null>

export type WorkspacePlaygroundTelemetryEvent = {
  type: WorkspacePlaygroundTelemetryEventType
  workspace_id?: string | null
  [key: string]: string | number | boolean | null | undefined
}

type WorkspacePlaygroundRecentEvent = {
  type: WorkspacePlaygroundTelemetryEventType
  at: number
  details: EventDetails
}

export type WorkspacePlaygroundTelemetryState = {
  version: 1
  counters: Record<WorkspacePlaygroundTelemetryEventType, number>
  last_event_at: number | null
  recent_events: WorkspacePlaygroundRecentEvent[]
}

export const WORKSPACE_PLAYGROUND_CONFUSION_EVENT_TYPES: WorkspacePlaygroundTelemetryEventType[] =
  [
    "confusion_retry_burst",
    "confusion_refresh_loop",
    "confusion_duplicate_submission"
  ]

export type WorkspacePlaygroundTelemetryQuery = {
  eventTypes?: WorkspacePlaygroundTelemetryEventType[]
  sinceMs?: number
}

export type WorkspacePlaygroundConfusionDashboardSnapshot = {
  counters: {
    retryBurst: number
    refreshLoop: number
    duplicateSubmission: number
  }
  rates: {
    retryPerStatusView: number
    refreshPerConflict: number
    duplicatePerStatusView: number
  }
  recentConfusionEvents: WorkspacePlaygroundRecentEvent[]
  windowedCounts: {
    last24h: number
    last7d: number
  }
}

const DEFAULT_COUNTERS: Record<WorkspacePlaygroundTelemetryEventType, number> = {
  status_viewed: 0,
  citation_provenance_opened: 0,
  token_cost_rendered: 0,
  diagnostics_toggled: 0,
  quota_warning_seen: 0,
  conflict_modal_opened: 0,
  undo_triggered: 0,
  operation_cancelled: 0,
  artifact_rehydrated_failed: 0,
  source_status_polled: 0,
  source_status_ready: 0,
  connectivity_state_changed: 0,
  confusion_retry_burst: 0,
  confusion_refresh_loop: 0,
  confusion_duplicate_submission: 0
}

const DEFAULT_STATE: WorkspacePlaygroundTelemetryState = {
  version: 1,
  counters: DEFAULT_COUNTERS,
  last_event_at: null,
  recent_events: []
}

const toEventDetails = (
  event: WorkspacePlaygroundTelemetryEvent
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
  async (): Promise<WorkspacePlaygroundTelemetryState> => {
    const raw = await storage.get<WorkspacePlaygroundTelemetryState | undefined>(
      WORKSPACE_PLAYGROUND_TELEMETRY_STORAGE_KEY
    )
    const state = raw && typeof raw === "object" ? raw : DEFAULT_STATE
    return {
      ...DEFAULT_STATE,
      ...state,
      counters: {
        ...DEFAULT_COUNTERS,
        ...(state.counters || {})
      },
      recent_events: Array.isArray(state.recent_events)
        ? state.recent_events.slice(-MAX_RECENT_EVENTS)
        : []
    }
  }

const writeTelemetryState = async (state: WorkspacePlaygroundTelemetryState) => {
  await storage.set(WORKSPACE_PLAYGROUND_TELEMETRY_STORAGE_KEY, state)
}

export const trackWorkspacePlaygroundTelemetry = async (
  event: WorkspacePlaygroundTelemetryEvent
) => {
  try {
    const state = await readTelemetryState()
    const now = Date.now()

    state.last_event_at = now
    state.counters[event.type] = (state.counters[event.type] || 0) + 1
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
    console.warn("[workspace-playground-telemetry] Failed to record event", error)
  }
}

export const getWorkspacePlaygroundTelemetryState =
  async (): Promise<WorkspacePlaygroundTelemetryState> => readTelemetryState()

export const resetWorkspacePlaygroundTelemetryState = async () => {
  await storage.set(WORKSPACE_PLAYGROUND_TELEMETRY_STORAGE_KEY, DEFAULT_STATE)
}

export const queryWorkspacePlaygroundTelemetryEvents = (
  state: WorkspacePlaygroundTelemetryState | null | undefined,
  query: WorkspacePlaygroundTelemetryQuery = {}
): WorkspacePlaygroundRecentEvent[] => {
  if (!state || !Array.isArray(state.recent_events)) return []

  const eventTypeFilter =
    Array.isArray(query.eventTypes) && query.eventTypes.length > 0
      ? new Set(query.eventTypes)
      : null
  const sinceMs =
    typeof query.sinceMs === "number" && Number.isFinite(query.sinceMs)
      ? query.sinceMs
      : null

  return state.recent_events
    .filter((event) => {
      if (!event || typeof event !== "object") return false
      if (eventTypeFilter && !eventTypeFilter.has(event.type)) return false
      if (sinceMs !== null && event.at < sinceMs) return false
      return true
    })
    .slice()
    .sort((a, b) => b.at - a.at)
}

const toFiniteRate = (numerator: number, denominator: number): number => {
  if (!Number.isFinite(numerator) || numerator <= 0) return 0
  if (!Number.isFinite(denominator) || denominator <= 0) return 0
  return numerator / denominator
}

export const buildWorkspacePlaygroundConfusionDashboardSnapshot = (
  state: WorkspacePlaygroundTelemetryState | null | undefined,
  now = Date.now()
): WorkspacePlaygroundConfusionDashboardSnapshot => {
  const counters = state?.counters || DEFAULT_COUNTERS
  const retryBurst = counters.confusion_retry_burst || 0
  const refreshLoop = counters.confusion_refresh_loop || 0
  const duplicateSubmission = counters.confusion_duplicate_submission || 0
  const statusViewed = counters.status_viewed || 0
  const conflictsOpened = counters.conflict_modal_opened || 0
  const confusionEvents = queryWorkspacePlaygroundTelemetryEvents(state, {
    eventTypes: WORKSPACE_PLAYGROUND_CONFUSION_EVENT_TYPES
  })

  return {
    counters: {
      retryBurst,
      refreshLoop,
      duplicateSubmission
    },
    rates: {
      retryPerStatusView: toFiniteRate(retryBurst, statusViewed),
      refreshPerConflict: toFiniteRate(refreshLoop, conflictsOpened),
      duplicatePerStatusView: toFiniteRate(duplicateSubmission, statusViewed)
    },
    recentConfusionEvents: confusionEvents.slice(0, 20),
    windowedCounts: {
      last24h: queryWorkspacePlaygroundTelemetryEvents(state, {
        eventTypes: WORKSPACE_PLAYGROUND_CONFUSION_EVENT_TYPES,
        sinceMs: now - 24 * 60 * 60 * 1000
      }).length,
      last7d: queryWorkspacePlaygroundTelemetryEvents(state, {
        eventTypes: WORKSPACE_PLAYGROUND_CONFUSION_EVENT_TYPES,
        sinceMs: now - 7 * 24 * 60 * 60 * 1000
      }).length
    }
  }
}

const escapeCsvCell = (value: unknown): string => {
  const text = String(value ?? "")
  if (text.includes(",") || text.includes("\"") || text.includes("\n")) {
    return `"${text.replace(/"/g, "\"\"")}"`
  }
  return text
}

export const buildWorkspacePlaygroundTelemetryEventsCsv = (
  events: WorkspacePlaygroundRecentEvent[]
): string => {
  const header = [
    "event_type",
    "timestamp_iso",
    "timestamp_ms",
    "workspace_id",
    "operation",
    "artifact_type",
    "retry_count",
    "refresh_count",
    "duplicate_count",
    "window_ms",
    "source_scope_count",
    "message_length",
    "details_json"
  ]

  const rows = events.map((event) => {
    const details = event.details || {}
    return [
      event.type,
      new Date(event.at).toISOString(),
      event.at,
      details.workspace_id ?? "",
      details.operation ?? "",
      details.artifact_type ?? "",
      details.retry_count ?? "",
      details.refresh_count ?? "",
      details.duplicate_count ?? "",
      details.window_ms ?? "",
      details.source_scope_count ?? "",
      details.message_length ?? "",
      JSON.stringify(details)
    ]
      .map((cell) => escapeCsvCell(cell))
      .join(",")
  })

  return [header.join(","), ...rows].join("\n")
}
