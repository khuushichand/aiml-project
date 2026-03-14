import React from "react"
import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import {
  PersonaTurnDetectionFeedbackCard
} from "../PersonaTurnDetectionFeedbackCard"
import type { PersonaVoiceAnalytics } from "../CommandAnalyticsSummary"

type MockRecentLiveSession = NonNullable<PersonaVoiceAnalytics["recent_live_sessions"]>[number]

const buildRecentLiveSession = (
  overrides: Partial<MockRecentLiveSession> = {}
): MockRecentLiveSession => ({
  session_id: "sess-1",
  started_at: "2026-03-13T17:00:00Z",
  ended_at: "2026-03-13T17:05:00Z",
  auto_commit_enabled: true,
  vad_threshold: 0.5,
  min_silence_ms: 250,
  turn_stop_secs: 0.2,
  min_utterance_secs: 0.4,
  turn_detection_changed_during_session: false,
  total_committed_turns: 4,
  vad_auto_commit_count: 4,
  manual_commit_count: 0,
  manual_mode_required_count: 0,
  text_only_tts_count: 0,
  listening_recovery_count: 0,
  thinking_recovery_count: 0,
  ...overrides
})

const buildAnalytics = (
  recentSessions: MockRecentLiveSession[]
): PersonaVoiceAnalytics => ({
  persona_id: "persona-1",
  summary: {
    total_events: 0,
    direct_command_count: 0,
    planner_fallback_count: 0,
    success_rate: 0,
    fallback_rate: 0,
    avg_response_time_ms: 0
  },
  live_voice: {
    total_committed_turns: recentSessions.reduce(
      (total, session) => total + session.total_committed_turns,
      0
    ),
    vad_auto_commit_count: recentSessions.reduce(
      (total, session) => total + session.vad_auto_commit_count,
      0
    ),
    manual_commit_count: recentSessions.reduce(
      (total, session) => total + session.manual_commit_count,
      0
    ),
    vad_auto_rate: 0,
    manual_commit_rate: 0,
    degraded_session_count: recentSessions.filter(
      (session) => session.manual_mode_required_count > 0
    ).length
  },
  commands: [],
  fallbacks: {
    total_invocations: 0,
    success_count: 0,
    error_count: 0,
    avg_response_time_ms: 0,
    last_used: null
  },
  recent_live_sessions: recentSessions
})

describe("PersonaTurnDetectionFeedbackCard", () => {
  it("uses total committed turns from recent sessions when summarizing signal", () => {
    render(
      <PersonaTurnDetectionFeedbackCard
        analytics={buildAnalytics([
          buildRecentLiveSession({ session_id: "sess-a" }),
          buildRecentLiveSession({ session_id: "sess-b" }),
          buildRecentLiveSession({ session_id: "sess-c" })
        ])}
      />
    )

    expect(
      screen.getByText("Suggestion: current settings look healthy")
    ).toBeInTheDocument()
    expect(
      screen.getByText("Based on 3 eligible sessions and 12 committed turns.")
    ).toBeInTheDocument()
  })

  it("clamps displayed signal percentages to the 0-100 range", () => {
    render(
      <PersonaTurnDetectionFeedbackCard
        analytics={buildAnalytics([
          buildRecentLiveSession({
            session_id: "sess-clamp-1",
            total_committed_turns: 1,
            vad_auto_commit_count: 3,
            manual_commit_count: 0,
            listening_recovery_count: 0,
            thinking_recovery_count: 0
          }),
          buildRecentLiveSession({
            session_id: "sess-clamp-2",
            total_committed_turns: 1,
            vad_auto_commit_count: 0,
            manual_commit_count: 3,
            listening_recovery_count: 0,
            thinking_recovery_count: 0
          }),
          buildRecentLiveSession({
            session_id: "sess-clamp-3",
            total_committed_turns: 1,
            vad_auto_commit_count: 0,
            manual_commit_count: 0,
            listening_recovery_count: 3,
            thinking_recovery_count: 0
          })
        ])}
      />
    )

    expect(screen.getByText("Auto-commit rate").parentElement).toHaveTextContent("100%")
    expect(screen.getByText("Manual sends").parentElement).toHaveTextContent("100%")
    expect(screen.getByText("Recovery signals").parentElement).toHaveTextContent("100%")
  })

  it("recomputes recent sessions when analytics changes but reuses the same session array", () => {
    const recentSessions = [
      buildRecentLiveSession({ session_id: "sess-initial-1" }),
      buildRecentLiveSession({ session_id: "sess-initial-2" }),
      buildRecentLiveSession({ session_id: "sess-initial-3" })
    ]

    const view = render(
      <PersonaTurnDetectionFeedbackCard analytics={buildAnalytics(recentSessions)} />
    )

    expect(screen.getByText("sess-initial-1")).toBeInTheDocument()

    recentSessions.splice(0, 1, buildRecentLiveSession({ session_id: "sess-updated-1" }))

    view.rerender(
      <PersonaTurnDetectionFeedbackCard analytics={buildAnalytics(recentSessions)} />
    )

    expect(screen.getByText("sess-updated-1")).toBeInTheDocument()
  })
})
