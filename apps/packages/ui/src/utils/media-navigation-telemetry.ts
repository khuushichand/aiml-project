import type { MediaNavigationResumeRestoreOutcome } from "@/utils/media-navigation-resume"
import { createSafeStorage } from "@/utils/safe-storage"

const storage = createSafeStorage({ area: "local" })

const TELEMETRY_STORAGE_KEY = "tldw:media:navigation:telemetry"
const MAX_RECENT_EVENTS = 200

type EventDetails = Record<string, string | number | boolean | null>

type RecentTelemetryEvent = {
  type: MediaNavigationTelemetryEvent["type"]
  at: number
  details: EventDetails
}

export type MediaNavigationFallbackKind = "no_structure" | "generated"
export type MediaNavigationRolloutControl =
  | "panel_visible"
  | "include_generated_fallback"

export type MediaNavigationTelemetryState = {
  version: 1
  counters: Record<string, number>
  blocked_url_schemes: Record<string, number>
  last_event_at: number | null
  last_resume_outcome: MediaNavigationResumeRestoreOutcome | null
  last_truncated_payload: {
    scope_key_hash: string
    media_id: string
    requested_max_nodes: number | null
    returned_node_count: number
    node_count: number
  } | null
  last_selection: {
    media_id: string
    node_id: string
    depth: number
    latency_ms: number
    source: "user" | "restore"
  } | null
  last_sanitization: {
    removed_node_count: number
    removed_attribute_count: number
    blocked_url_count: number
  } | null
  last_fallback: {
    scope_key_hash: string
    media_id: string
    fallback_kind: MediaNavigationFallbackKind
    source: string | null
  } | null
  last_rollout_control: {
    scope_key_hash: string
    media_id: string | null
    control: MediaNavigationRolloutControl
    enabled: boolean
  } | null
  recent_events: RecentTelemetryEvent[]
}

export type MediaNavigationTelemetryEvent =
  | {
      type: "media_navigation_payload_truncated"
      scope_key_hash: string
      media_id: string | number
      requested_max_nodes?: number | null
      returned_node_count: number
      node_count: number
    }
  | {
      type: "media_navigation_resume_state_restored"
      scope_key_hash: string
      media_id: string | number
      outcome: MediaNavigationResumeRestoreOutcome
    }
  | {
      type: "media_navigation_resume_state_evicted"
      scope_key_hash: string
      evicted_entry_count: number
      reason: "lru" | "stale"
    }
  | {
      type: "media_navigation_section_selected"
      media_id: string | number
      node_id: string
      depth: number
      latency_ms: number
      source: "user" | "restore"
    }
  | {
      type: "media_navigation_fallback_used"
      scope_key_hash: string
      media_id: string | number
      fallback_kind: MediaNavigationFallbackKind
      source?: string | null
    }
  | {
      type: "media_navigation_rollout_control_changed"
      scope_key_hash: string
      media_id?: string | number | null
      control: MediaNavigationRolloutControl
      enabled: boolean
    }
  | {
      type: "media_rich_sanitization_applied"
      removed_node_count: number
      removed_attribute_count: number
      blocked_url_count: number
    }
  | {
      type: "media_rich_sanitization_blocked_url"
      scheme: string
    }

const DEFAULT_STATE: MediaNavigationTelemetryState = {
  version: 1,
  counters: {},
  blocked_url_schemes: {},
  last_event_at: null,
  last_resume_outcome: null,
  last_truncated_payload: null,
  last_selection: null,
  last_sanitization: null,
  last_fallback: null,
  last_rollout_control: null,
  recent_events: []
}

const toEventDetails = (
  event: MediaNavigationTelemetryEvent
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

const readTelemetryState = async (): Promise<MediaNavigationTelemetryState> => {
  const raw = await storage.get<MediaNavigationTelemetryState | undefined>(
    TELEMETRY_STORAGE_KEY
  )
  const state = raw && typeof raw === "object" ? raw : DEFAULT_STATE
  return {
    ...DEFAULT_STATE,
    ...state,
    counters: { ...DEFAULT_STATE.counters, ...(state.counters || {}) },
    blocked_url_schemes: {
      ...DEFAULT_STATE.blocked_url_schemes,
      ...(state.blocked_url_schemes || {})
    },
    recent_events: Array.isArray(state.recent_events)
      ? state.recent_events.slice(-MAX_RECENT_EVENTS)
      : []
  }
}

const writeTelemetryState = async (state: MediaNavigationTelemetryState) => {
  await storage.set(TELEMETRY_STORAGE_KEY, state)
}

const incrementCounter = (
  counters: Record<string, number>,
  eventType: MediaNavigationTelemetryEvent["type"]
) => {
  counters[eventType] = (counters[eventType] || 0) + 1
}

export const hashMediaNavigationScopeKey = (scopeKey: string): string => {
  const input = String(scopeKey || "")
  let hash = 2166136261
  for (let i = 0; i < input.length; i += 1) {
    hash ^= input.charCodeAt(i)
    hash +=
      (hash << 1) +
      (hash << 4) +
      (hash << 7) +
      (hash << 8) +
      (hash << 24)
  }
  return (hash >>> 0).toString(36)
}

export const trackMediaNavigationTelemetry = async (
  event: MediaNavigationTelemetryEvent
) => {
  try {
    const state = await readTelemetryState()
    const now = Date.now()

    state.last_event_at = now
    incrementCounter(state.counters, event.type)

    switch (event.type) {
      case "media_navigation_payload_truncated":
        state.last_truncated_payload = {
          scope_key_hash: event.scope_key_hash,
          media_id: String(event.media_id),
          requested_max_nodes:
            typeof event.requested_max_nodes === "number"
              ? event.requested_max_nodes
              : null,
          returned_node_count: event.returned_node_count,
          node_count: event.node_count
        }
        break
      case "media_navigation_resume_state_restored":
        state.last_resume_outcome = event.outcome
        break
      case "media_navigation_resume_state_evicted":
        // Counters capture event totals; this stores no additional state.
        break
      case "media_navigation_section_selected":
        state.last_selection = {
          media_id: String(event.media_id),
          node_id: event.node_id,
          depth: event.depth,
          latency_ms: event.latency_ms,
          source: event.source
        }
        break
      case "media_navigation_fallback_used":
        state.last_fallback = {
          scope_key_hash: event.scope_key_hash,
          media_id: String(event.media_id),
          fallback_kind: event.fallback_kind,
          source:
            typeof event.source === "string" && event.source.trim().length > 0
              ? event.source
              : null
        }
        break
      case "media_navigation_rollout_control_changed":
        state.last_rollout_control = {
          scope_key_hash: event.scope_key_hash,
          media_id:
            event.media_id === null || event.media_id === undefined
              ? null
              : String(event.media_id),
          control: event.control,
          enabled: Boolean(event.enabled)
        }
        break
      case "media_rich_sanitization_applied":
        state.last_sanitization = {
          removed_node_count: event.removed_node_count,
          removed_attribute_count: event.removed_attribute_count,
          blocked_url_count: event.blocked_url_count
        }
        break
      case "media_rich_sanitization_blocked_url": {
        const scheme = String(event.scheme || "").trim().toLowerCase() || "unknown"
        state.blocked_url_schemes[scheme] =
          (state.blocked_url_schemes[scheme] || 0) + 1
        break
      }
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
    console.warn("[media-navigation-telemetry] Failed to record event", error)
  }
}
