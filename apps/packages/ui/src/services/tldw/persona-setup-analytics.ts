import { tldwClient } from "./TldwApiClient"

export type PersonaSetupAnalyticsEventType =
  | "setup_started"
  | "step_viewed"
  | "step_completed"
  | "step_error"
  | "retry_clicked"
  | "detour_started"
  | "detour_returned"
  | "setup_completed"
  | "handoff_action_clicked"
  | "handoff_target_reached"
  | "handoff_dismissed"
  | "first_post_setup_action"

export type PersonaSetupAnalyticsEvent = {
  eventId?: string
  runId: string
  eventType: PersonaSetupAnalyticsEventType
  step?: "persona" | "voice" | "commands" | "safety" | "test"
  completionType?: "dry_run" | "live_session"
  detourSource?: string | null
  actionTarget?: string | null
  metadata?: Record<string, unknown>
}

const createEventId = (): string => {
  if (typeof globalThis !== "undefined" && typeof globalThis.crypto?.randomUUID === "function") {
    return globalThis.crypto.randomUUID()
  }
  return `setup-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

export const buildSetupEventKey = ({
  eventType,
  step,
  detourSource,
  actionTarget,
  metadata
}: Pick<
  PersonaSetupAnalyticsEvent,
  "eventType" | "step" | "detourSource" | "actionTarget" | "metadata"
>):
  | string
  | undefined => {
  if (eventType === "setup_started") return "setup_started"
  if (eventType === "setup_completed") return "setup_completed"
  if (eventType === "handoff_dismissed") return "handoff_dismissed"
  if (eventType === "first_post_setup_action") return "first_post_setup_action"
  if (eventType === "handoff_target_reached" && actionTarget) {
    const metadataRecord =
      metadata && typeof metadata === "object" ? metadata : undefined
    const connectionId = String(metadataRecord?.connection_id || "").trim()
    if (connectionId) {
      return `handoff_target_reached:${actionTarget}:${connectionId}`
    }
    const connectionName = String(metadataRecord?.connection_name || "").trim()
    if (connectionName) {
      return `handoff_target_reached:${actionTarget}:${connectionName}`
    }
    return `handoff_target_reached:${actionTarget}`
  }
  if (eventType === "step_viewed" && step) return `step_viewed:${step}`
  if (eventType === "step_completed" && step) return `step_completed:${step}`
  if (eventType === "detour_returned" && detourSource) {
    return `detour_returned:${detourSource}`
  }
  return undefined
}

export const postPersonaSetupEvent = async (
  personaId: string,
  event: PersonaSetupAnalyticsEvent
): Promise<boolean> => {
  const normalizedPersonaId = String(personaId || "").trim()
  const normalizedRunId = String(event.runId || "").trim()
  if (!normalizedPersonaId || !normalizedRunId) return false

  try {
    const response = await tldwClient.fetchWithAuth(
      `/api/v1/persona/profiles/${encodeURIComponent(normalizedPersonaId)}/setup-events` as any,
      {
        method: "POST",
        body: {
          event_id: String(event.eventId || createEventId()),
          event_key: buildSetupEventKey(event),
          run_id: normalizedRunId,
          event_type: event.eventType,
          step: event.step,
          completion_type: event.completionType,
          detour_source: event.detourSource || undefined,
          action_target: event.actionTarget || undefined,
          metadata: event.metadata || {}
        }
      }
    )
    return Boolean(response?.ok)
  } catch {
    return false
  }
}
