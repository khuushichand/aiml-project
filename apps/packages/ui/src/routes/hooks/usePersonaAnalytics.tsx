import React from "react"

import type { PersonaVoiceAnalytics } from "@/components/PersonaGarden/CommandAnalyticsSummary"
import type { PersonaSetupAnalyticsResponse } from "@/components/PersonaGarden/PersonaSetupAnalyticsCard"
import {
  buildSetupEventKey,
  postPersonaSetupEvent,
  type PersonaSetupAnalyticsEvent,
  type PersonaSetupAnalyticsEventType,
} from "@/services/tldw/persona-setup-analytics"
import { toAllowedPath } from "@/services/tldw/path-utils"
import { tldwClient } from "@/services/tldw/TldwApiClient"

import type { PersonaGardenTabKey } from "@/utils/persona-garden-route"

export interface UsePersonaAnalyticsDeps {
  selectedPersonaId: string
  activeTab: PersonaGardenTabKey
  currentSetupRunId: string | null
}

export function usePersonaAnalytics(deps: UsePersonaAnalyticsDeps) {
  const { selectedPersonaId, activeTab, currentSetupRunId } = deps

  const emittedSetupEventKeysRef = React.useRef<Set<string>>(new Set())

  const [voiceAnalytics, setVoiceAnalytics] =
    React.useState<PersonaVoiceAnalytics | null>(null)
  const [voiceAnalyticsLoading, setVoiceAnalyticsLoading] =
    React.useState(false)
  const [setupAnalytics, setSetupAnalytics] =
    React.useState<PersonaSetupAnalyticsResponse | null>(null)
  const [setupAnalyticsLoading, setSetupAnalyticsLoading] =
    React.useState(false)

  const liveVoiceAnalyticsSnapshotRef = React.useRef<{
    personaId: string
    sessionId: string
    listeningRecoveryCount: number
    thinkingRecoveryCount: number
  }>({
    personaId: "",
    sessionId: "",
    listeningRecoveryCount: 0,
    thinkingRecoveryCount: 0,
  })

  // ── emitSetupAnalyticsEvent ──

  const emitSetupAnalyticsEvent = React.useCallback(
    (
      event: Omit<PersonaSetupAnalyticsEvent, "runId"> & {
        runId?: string
        personaId?: string
      }
    ) => {
      const personaId = String(
        event.personaId || selectedPersonaId || ""
      ).trim()
      const runId = String(
        event.runId || currentSetupRunId || ""
      ).trim()
      if (!personaId || !runId) return

      const eventType = event.eventType as PersonaSetupAnalyticsEventType
      const eventKey = buildSetupEventKey({
        eventType,
        step: event.step,
        detourSource: event.detourSource || undefined,
        actionTarget: event.actionTarget || undefined,
        metadata: event.metadata,
      })
      if (eventKey) {
        const dedupeKey = `${personaId}:${runId}:${eventKey}`
        if (emittedSetupEventKeysRef.current.has(dedupeKey)) return
        emittedSetupEventKeysRef.current.add(dedupeKey)
      }

      void postPersonaSetupEvent(personaId, {
        runId,
        eventType,
        step: event.step,
        completionType: event.completionType,
        detourSource: event.detourSource || undefined,
        actionTarget: event.actionTarget || undefined,
        metadata: event.metadata,
      })
    },
    [currentSetupRunId, selectedPersonaId]
  )

  // ── Live voice analytics flush ──

  const flushLiveVoiceSessionAnalytics = React.useCallback(
    (options?: { finalize?: boolean }) => {
      const snapshot = liveVoiceAnalyticsSnapshotRef.current
      const personaId = String(snapshot.personaId || "").trim()
      const activeSessionId = String(snapshot.sessionId || "").trim()
      if (!personaId || !activeSessionId) return
      void tldwClient
        .fetchWithAuth(
          `/api/v1/persona/profiles/${encodeURIComponent(
            personaId
          )}/voice-analytics/live-sessions/${encodeURIComponent(
            activeSessionId
          )}` as any,
          {
            method: "PUT",
            body: {
              listening_recovery_count: snapshot.listeningRecoveryCount,
              thinking_recovery_count: snapshot.thinkingRecoveryCount,
              finalize: options?.finalize === true,
            },
          }
        )
        .catch(() => {
          // Best-effort flush only
        })
    },
    []
  )

  // ── Load voice analytics when on relevant tabs ──

  React.useEffect(() => {
    let cancelled = false
    const normalizedPersonaId = String(selectedPersonaId || "").trim()
    const shouldLoad =
      normalizedPersonaId.length > 0 &&
      (activeTab === "commands" ||
        activeTab === "test-lab" ||
        activeTab === "profiles")

    if (!normalizedPersonaId) {
      setVoiceAnalytics(null)
      setVoiceAnalyticsLoading(false)
      return
    }
    if (!shouldLoad) return

    if (voiceAnalytics?.persona_id !== normalizedPersonaId) {
      setVoiceAnalytics(null)
    }
    setVoiceAnalyticsLoading(true)

    const loadVoiceAnalytics = async () => {
      try {
        const response = await tldwClient.fetchWithAuth(
          `/api/v1/persona/profiles/${encodeURIComponent(
            normalizedPersonaId
          )}/voice-analytics?days=7` as any,
          { method: "GET" }
        )
        if (!response.ok) {
          throw new Error(
            response.error || "Failed to load persona voice analytics."
          )
        }
        const payload =
          (await response.json()) as PersonaVoiceAnalytics
        if (!cancelled) {
          setVoiceAnalytics(payload)
        }
      } catch {
        if (!cancelled) {
          setVoiceAnalytics(null)
        }
      } finally {
        if (!cancelled) {
          setVoiceAnalyticsLoading(false)
        }
      }
    }

    void loadVoiceAnalytics()
    return () => {
      cancelled = true
    }
  }, [activeTab, selectedPersonaId])

  // ── Load setup analytics when on profiles tab ──

  React.useEffect(() => {
    let cancelled = false
    const normalizedPersonaId = String(selectedPersonaId || "").trim()

    if (!normalizedPersonaId) {
      setSetupAnalytics(null)
      setSetupAnalyticsLoading(false)
      return
    }

    if (setupAnalytics?.persona_id !== normalizedPersonaId) {
      setSetupAnalytics(null)
    }

    if (activeTab !== "profiles") {
      setSetupAnalyticsLoading(false)
      return
    }

    setSetupAnalyticsLoading(true)

    const loadSetupAnalytics = async () => {
      try {
        const response = await tldwClient.fetchWithAuth(
          toAllowedPath(
            `/api/v1/persona/profiles/${encodeURIComponent(
              normalizedPersonaId
            )}/setup-analytics?days=30&limit=5`
          ),
          { method: "GET" }
        )
        if (!response.ok) {
          throw new Error(
            response.error || "Failed to load persona setup analytics."
          )
        }
        const payload =
          (await response.json()) as PersonaSetupAnalyticsResponse
        if (!cancelled) {
          setSetupAnalytics(payload)
        }
      } catch (fetchError) {
        console.warn(
          "tldw_server: failed to load persona setup analytics",
          {
            personaId: normalizedPersonaId,
            error: fetchError,
          }
        )
        if (!cancelled) {
          setSetupAnalytics(null)
        }
      } finally {
        if (!cancelled) {
          setSetupAnalyticsLoading(false)
        }
      }
    }

    void loadSetupAnalytics()
    return () => {
      cancelled = true
    }
  }, [activeTab, selectedPersonaId])

  return {
    // state
    voiceAnalytics,
    voiceAnalyticsLoading,
    setupAnalytics,
    setupAnalyticsLoading,
    // refs
    liveVoiceAnalyticsSnapshotRef,
    emittedSetupEventKeysRef,
    // callbacks
    emitSetupAnalyticsEvent,
    flushLiveVoiceSessionAnalytics,
  }
}
