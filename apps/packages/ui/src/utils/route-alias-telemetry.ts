import { createSafeStorage } from "@/utils/safe-storage"

const storage = createSafeStorage({ area: "local" })

export const ROUTE_ALIAS_TELEMETRY_STORAGE_KEY = "tldw:route:alias:telemetry"
const MAX_RECENT_EVENTS = 200

type EventDetails = Record<string, string | number | boolean | null>

type RouteAliasTelemetryRecentEvent = {
  type: RouteAliasTelemetryEvent["type"]
  at: number
  details: EventDetails
}

export type RouteAliasTelemetryState = {
  version: 1
  counters: Record<string, number>
  alias_hits: Record<string, number>
  destination_hits: Record<string, number>
  last_event_at: number | null
  last_redirect: {
    source_path: string
    destination_path: string
    preserve_params: boolean
    query_or_hash_carried: boolean
  } | null
  recent_events: RouteAliasTelemetryRecentEvent[]
}

type RouteParts = {
  pathname: string
  hasQuery: boolean
  hasHash: boolean
}

export type RouteAliasRedirectPayload = {
  sourcePath: string
  destinationPath: string
  preserveParams: boolean
}

export type RouteAliasTelemetryEvent = {
  type: "route_alias_redirect"
  source_path: string
  destination_path: string
  preserve_params: boolean
  source_has_query: boolean
  source_has_hash: boolean
  destination_has_query: boolean
  destination_has_hash: boolean
  query_or_hash_carried: boolean
}

const DEFAULT_STATE: RouteAliasTelemetryState = {
  version: 1,
  counters: {},
  alias_hits: {},
  destination_hits: {},
  last_event_at: null,
  last_redirect: null,
  recent_events: []
}

const normalizeInputPath = (input: string): string => {
  const trimmed = String(input || "").trim()
  if (!trimmed) return "/"

  try {
    const parsed = new URL(trimmed)
    const path = `${parsed.pathname}${parsed.search}${parsed.hash}`
    return path || "/"
  } catch {
    // Not an absolute URL; treat as app-relative path.
  }

  return trimmed.startsWith("/") ? trimmed : `/${trimmed}`
}

const splitRouteParts = (input: string): RouteParts => {
  const normalized = normalizeInputPath(input)
  const queryIndex = normalized.indexOf("?")
  const hashIndex = normalized.indexOf("#")

  let end = normalized.length
  if (queryIndex >= 0) end = Math.min(end, queryIndex)
  if (hashIndex >= 0) end = Math.min(end, hashIndex)

  let pathname = normalized.slice(0, end) || "/"
  if (pathname.length > 1 && pathname.endsWith("/")) {
    pathname = pathname.replace(/\/+$/, "") || "/"
  }

  return {
    pathname,
    hasQuery: queryIndex >= 0,
    hasHash: hashIndex >= 0
  }
}

export const buildRouteAliasTelemetryEvent = (
  payload: RouteAliasRedirectPayload
): RouteAliasTelemetryEvent => {
  const source = splitRouteParts(payload.sourcePath)
  const destination = splitRouteParts(payload.destinationPath)
  const queryOrHashCarried =
    (source.hasQuery && destination.hasQuery) ||
    (source.hasHash && destination.hasHash)

  return {
    type: "route_alias_redirect",
    source_path: source.pathname,
    destination_path: destination.pathname,
    preserve_params: Boolean(payload.preserveParams),
    source_has_query: source.hasQuery,
    source_has_hash: source.hasHash,
    destination_has_query: destination.hasQuery,
    destination_has_hash: destination.hasHash,
    query_or_hash_carried: queryOrHashCarried
  }
}

const toEventDetails = (event: RouteAliasTelemetryEvent): EventDetails => {
  const details: EventDetails = {}

  for (const [key, value] of Object.entries(event)) {
    if (key === "type") continue
    details[key] = value
  }

  return details
}

const readTelemetryState = async (): Promise<RouteAliasTelemetryState> => {
  const raw = await storage.get<RouteAliasTelemetryState | undefined>(
    ROUTE_ALIAS_TELEMETRY_STORAGE_KEY
  )
  const state = raw && typeof raw === "object" ? raw : DEFAULT_STATE

  return {
    ...DEFAULT_STATE,
    ...state,
    counters: { ...DEFAULT_STATE.counters, ...(state.counters || {}) },
    alias_hits: { ...DEFAULT_STATE.alias_hits, ...(state.alias_hits || {}) },
    destination_hits: {
      ...DEFAULT_STATE.destination_hits,
      ...(state.destination_hits || {})
    },
    recent_events: Array.isArray(state.recent_events)
      ? state.recent_events.slice(-MAX_RECENT_EVENTS)
      : []
  }
}

const incrementCounter = (
  counters: Record<string, number>,
  key: RouteAliasTelemetryEvent["type"]
) => {
  counters[key] = (counters[key] || 0) + 1
}

const writeTelemetryState = async (state: RouteAliasTelemetryState) => {
  await storage.set(ROUTE_ALIAS_TELEMETRY_STORAGE_KEY, state)
}

export const trackRouteAliasRedirect = async (
  payload: RouteAliasRedirectPayload
) => {
  try {
    const event = buildRouteAliasTelemetryEvent(payload)
    const now = Date.now()
    const state = await readTelemetryState()

    incrementCounter(state.counters, event.type)
    state.alias_hits[event.source_path] =
      (state.alias_hits[event.source_path] || 0) + 1
    state.destination_hits[event.destination_path] =
      (state.destination_hits[event.destination_path] || 0) + 1

    state.last_event_at = now
    state.last_redirect = {
      source_path: event.source_path,
      destination_path: event.destination_path,
      preserve_params: event.preserve_params,
      query_or_hash_carried: event.query_or_hash_carried
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
    console.warn("[route-alias-telemetry] Failed to record alias redirect", error)
  }
}
