import React from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  fetchWithAuth: vi.fn(),
  resolvedDefaults: {
    sttLanguage: "en-US",
    sttModel: "parakeet",
    ttsProvider: "tldw",
    ttsVoice: "af_heart",
    confirmationMode: "destructive_only" as const,
    voiceChatTriggerPhrases: ["hey helper"],
    autoResume: true,
    bargeIn: false,
    autoCommitEnabled: true,
    vadThreshold: 0.5,
    minSilenceMs: 250,
    turnStopSecs: 0.2,
    minUtteranceSecs: 0.4
  }
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      defaultValueOrOptions?:
        | string
        | {
            defaultValue?: string
          }
    ) => {
      if (typeof defaultValueOrOptions === "string") return defaultValueOrOptions
      if (defaultValueOrOptions?.defaultValue) return defaultValueOrOptions.defaultValue
      return key
    }
  })
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    fetchWithAuth: (...args: unknown[]) =>
      (mocks.fetchWithAuth as (...args: unknown[]) => unknown)(...args)
  }
}))

vi.mock("@/hooks/useResolvedPersonaVoiceDefaults", () => ({
  PERSONA_TURN_DETECTION_BALANCED_DEFAULTS: {
    autoCommitEnabled: true,
    vadThreshold: 0.5,
    minSilenceMs: 250,
    turnStopSecs: 0.2,
    minUtteranceSecs: 0.4
  },
  useResolvedPersonaVoiceDefaults: () => mocks.resolvedDefaults
}))

import { AssistantDefaultsPanel } from "../AssistantDefaultsPanel"

type MockRecentLiveSession = {
  session_id: string
  started_at: string
  ended_at: string
  auto_commit_enabled: boolean
  vad_threshold: number
  min_silence_ms: number
  turn_stop_secs: number
  min_utterance_secs: number
  turn_detection_changed_during_session: boolean
  committed_turn_count: number
  vad_auto_commit_count: number
  manual_commit_count: number
  manual_mode_required_count: number
  text_only_tts_count: number
  listening_recovery_count: number
  thinking_recovery_count: number
}

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
  committed_turn_count: 4,
  vad_auto_commit_count: 4,
  manual_commit_count: 0,
  manual_mode_required_count: 0,
  text_only_tts_count: 0,
  listening_recovery_count: 0,
  thinking_recovery_count: 0,
  ...overrides
})

const buildVoiceAnalytics = (recentSessions: MockRecentLiveSession[]) => ({
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
      (total, session) => total + session.committed_turn_count,
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

describe("AssistantDefaultsPanel", () => {
  beforeEach(() => {
    mocks.fetchWithAuth.mockReset()
    mocks.resolvedDefaults = {
      sttLanguage: "en-US",
      sttModel: "parakeet",
      ttsProvider: "tldw",
      ttsVoice: "af_heart",
      confirmationMode: "destructive_only",
      voiceChatTriggerPhrases: ["hey helper"],
      autoResume: true,
      bargeIn: false,
      autoCommitEnabled: true,
      vadThreshold: 0.5,
      minSilenceMs: 250,
      turnStopSecs: 0.2,
      minUtteranceSecs: 0.4
    }
    mocks.fetchWithAuth.mockImplementation((path: string, init?: { method?: string; body?: any }) => {
      if (
        path === "/api/v1/persona/profiles/persona-1" &&
        String(init?.method || "GET").toUpperCase() === "GET"
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: "persona-1",
            voice_defaults: {
              stt_language: "en-US",
              stt_model: "whisper-1",
              tts_provider: "tldw",
              tts_voice: "af_heart",
              confirmation_mode: "destructive_only",
              voice_chat_trigger_phrases: ["hey helper"],
              auto_resume: true,
              barge_in: false,
              auto_commit_enabled: true,
              vad_threshold: 0.35,
              min_silence_ms: 150,
              turn_stop_secs: 0.1,
              min_utterance_secs: 0.25
            }
          })
        })
      }
      if (
        path === "/api/v1/persona/profiles/persona-1" &&
        String(init?.method || "").toUpperCase() === "PATCH"
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: "persona-1",
            voice_defaults: init?.body?.voice_defaults
          })
        })
      }
      return Promise.resolve({
        ok: false,
        error: `unhandled path: ${path}`,
        json: async () => ({})
      })
    })
  })

  it("loads persona defaults, explains fallback behavior, and saves edits", async () => {
    const onSaved = vi.fn()
    render(
      <AssistantDefaultsPanel
        selectedPersonaId="persona-1"
        selectedPersonaName="Helper"
        isActive
        onSaved={onSaved}
      />
    )

    expect(
      screen.getByText(
        "Persona defaults stay separate from browser-wide fallback settings. The preview below shows the effective values after local fallback is applied."
      )
    ).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByLabelText("STT language")).toHaveValue("en-US")
      expect(screen.getByLabelText("STT model")).toHaveValue("whisper-1")
    })
    expect(screen.getByText("Turn detection defaults")).toBeInTheDocument()
    expect(screen.getByTestId("assistant-defaults-vad-auto-commit")).toBeChecked()

    fireEvent.click(screen.getByTestId("assistant-defaults-vad-advanced-toggle"))
    expect(screen.getByTestId("assistant-defaults-vad-threshold")).toHaveValue(0.35)
    expect(screen.getByTestId("assistant-defaults-vad-min-silence-ms")).toHaveValue(150)
    expect(screen.getByTestId("assistant-defaults-vad-turn-stop-secs")).toHaveValue(0.1)
    expect(screen.getByTestId("assistant-defaults-vad-min-utterance-secs")).toHaveValue(0.25)

    fireEvent.change(screen.getByLabelText("STT language"), {
      target: { value: "fr-FR" }
    })
    fireEvent.change(screen.getByLabelText("TTS provider"), {
      target: { value: "openai" }
    })
    fireEvent.change(screen.getByLabelText("TTS voice"), {
      target: { value: "nova" }
    })
    fireEvent.change(screen.getByLabelText("Trigger phrases"), {
      target: { value: "bonjour helper\nsalut helper" }
    })
    fireEvent.change(screen.getByLabelText("Auto-resume"), {
      target: { value: "false" }
    })
    fireEvent.change(screen.getByLabelText("Barge-in"), {
      target: { value: "true" }
    })
    fireEvent.click(screen.getByTestId("assistant-defaults-vad-auto-commit"))
    fireEvent.change(screen.getByTestId("assistant-defaults-vad-threshold"), {
      target: { value: "0.61" }
    })
    fireEvent.change(screen.getByTestId("assistant-defaults-vad-min-silence-ms"), {
      target: { value: "640" }
    })
    fireEvent.change(screen.getByTestId("assistant-defaults-vad-turn-stop-secs"), {
      target: { value: "0.48" }
    })
    fireEvent.change(screen.getByTestId("assistant-defaults-vad-min-utterance-secs"), {
      target: { value: "0.82" }
    })
    fireEvent.click(screen.getByRole("button", { name: "Save assistant defaults" }))

    await waitFor(() => {
      expect(mocks.fetchWithAuth).toHaveBeenCalledWith(
        "/api/v1/persona/profiles/persona-1",
        {
          method: "PATCH",
          body: {
            voice_defaults: {
              stt_language: "fr-FR",
              stt_model: "whisper-1",
              tts_provider: "openai",
              tts_voice: "nova",
              confirmation_mode: "destructive_only",
              voice_chat_trigger_phrases: ["bonjour helper", "salut helper"],
              auto_resume: false,
              barge_in: true,
              auto_commit_enabled: false,
              vad_threshold: 0.61,
              min_silence_ms: 640,
              turn_stop_secs: 0.48,
              min_utterance_secs: 0.82
            }
          }
        }
      )
    })

    expect(screen.getByText("Assistant defaults saved.")).toBeInTheDocument()
    expect(screen.getByText("Effective Preview")).toBeInTheDocument()
    expect(screen.getByText("parakeet")).toBeInTheDocument()
    expect(onSaved).toHaveBeenCalledWith(
      expect.objectContaining({
        stt_language: "fr-FR"
      })
    )
  })

  it("shows custom as the saved preset when advanced turn detection values diverge", async () => {
    mocks.fetchWithAuth.mockImplementation((path: string, init?: { method?: string; body?: any }) => {
      if (
        path === "/api/v1/persona/profiles/persona-1" &&
        String(init?.method || "GET").toUpperCase() === "GET"
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: "persona-1",
            voice_defaults: {
              stt_language: "en-US",
              stt_model: "whisper-1",
              tts_provider: "tldw",
              tts_voice: "af_heart",
              confirmation_mode: "destructive_only",
              voice_chat_trigger_phrases: ["hey helper"],
              auto_resume: true,
              barge_in: false,
              auto_commit_enabled: false,
              vad_threshold: 0.61,
              min_silence_ms: 640,
              turn_stop_secs: 0.48,
              min_utterance_secs: 0.82
            }
          })
        })
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({
          id: "persona-1",
          voice_defaults: init?.body?.voice_defaults
        })
      })
    })

    render(
      <AssistantDefaultsPanel
        selectedPersonaId="persona-1"
        selectedPersonaName="Helper"
        isActive
      />
    )

    await waitFor(() => {
      expect(
        screen.getByTestId("assistant-defaults-vad-preset-custom")
      ).toHaveAttribute("data-active", "true")
    })
  })

  it("shows no tuning suggestion yet when recent eligible data is sparse", async () => {
    render(
      <AssistantDefaultsPanel
        selectedPersonaId="persona-1"
        selectedPersonaName="Helper"
        isActive
        analytics={buildVoiceAnalytics([
          buildRecentLiveSession({ session_id: "sess-sparse-1" }),
          buildRecentLiveSession({ session_id: "sess-sparse-2" })
        ])}
      />
    )

    await waitFor(() => {
      expect(screen.getByText("Recent live tuning feedback")).toBeInTheDocument()
    })

    expect(screen.getByText("Current signal")).toBeInTheDocument()
    expect(screen.getByText("No tuning suggestion yet")).toBeInTheDocument()
    expect(
      screen.getByText("Run a few live sessions to unlock guidance.")
    ).toBeInTheDocument()
  })

  it("shows a healthy-state suggestion when recent sessions look stable", async () => {
    render(
      <AssistantDefaultsPanel
        selectedPersonaId="persona-1"
        selectedPersonaName="Helper"
        isActive
        analytics={buildVoiceAnalytics([
          buildRecentLiveSession({ session_id: "sess-healthy-1" }),
          buildRecentLiveSession({ session_id: "sess-healthy-2" }),
          buildRecentLiveSession({ session_id: "sess-healthy-3" })
        ])}
      />
    )

    await waitFor(() => {
      expect(
        screen.getByText("Suggestion: current settings look healthy")
      ).toBeInTheDocument()
    })
  })

  it("suggests trying Fast when manual sends stay high across eligible sessions", async () => {
    render(
      <AssistantDefaultsPanel
        selectedPersonaId="persona-1"
        selectedPersonaName="Helper"
        isActive
        analytics={buildVoiceAnalytics([
          buildRecentLiveSession({
            session_id: "sess-fast-1",
            committed_turn_count: 4,
            vad_auto_commit_count: 2,
            manual_commit_count: 2
          }),
          buildRecentLiveSession({
            session_id: "sess-fast-2",
            committed_turn_count: 4,
            vad_auto_commit_count: 2,
            manual_commit_count: 2
          }),
          buildRecentLiveSession({
            session_id: "sess-fast-3",
            committed_turn_count: 4,
            vad_auto_commit_count: 2,
            manual_commit_count: 2
          })
        ])}
      />
    )

    await waitFor(() => {
      expect(
        screen.getByText("Suggestion: try Fast for quicker commits")
      ).toBeInTheDocument()
    })
  })

  it("suggests checking auto-commit availability before changing thresholds", async () => {
    render(
      <AssistantDefaultsPanel
        selectedPersonaId="persona-1"
        selectedPersonaName="Helper"
        isActive
        analytics={buildVoiceAnalytics([
          buildRecentLiveSession({
            session_id: "sess-manual-mode-1",
            committed_turn_count: 4,
            vad_auto_commit_count: 1,
            manual_commit_count: 3,
            manual_mode_required_count: 1
          }),
          buildRecentLiveSession({
            session_id: "sess-manual-mode-2",
            committed_turn_count: 4,
            vad_auto_commit_count: 2,
            manual_commit_count: 2,
            manual_mode_required_count: 1
          }),
          buildRecentLiveSession({
            session_id: "sess-manual-mode-3",
            committed_turn_count: 4,
            vad_auto_commit_count: 2,
            manual_commit_count: 2,
            manual_mode_required_count: 1
          })
        ])}
      />
    )

    await waitFor(() => {
      expect(
        screen.getByText("Suggestion: check auto-commit availability first")
      ).toBeInTheDocument()
    })
  })

  it("marks mixed sessions and excludes them from recommendation heuristics", async () => {
    render(
      <AssistantDefaultsPanel
        selectedPersonaId="persona-1"
        selectedPersonaName="Helper"
        isActive
        analytics={buildVoiceAnalytics([
          buildRecentLiveSession({ session_id: "sess-mixed-1" }),
          buildRecentLiveSession({ session_id: "sess-mixed-2" }),
          buildRecentLiveSession({
            session_id: "sess-mixed-3",
            turn_detection_changed_during_session: true,
            committed_turn_count: 4,
            vad_auto_commit_count: 1,
            manual_commit_count: 3,
            manual_mode_required_count: 2
          })
        ])}
      />
    )

    await waitFor(() => {
      expect(screen.getByText("Mixed session")).toBeInTheDocument()
    })

    expect(
      screen.getByTestId("persona-turn-detection-feedback-mixed-note")
    ).toHaveTextContent("1 mixed recent session excluded from suggestions")
    expect(
      screen.getByText("Suggestion: current settings look healthy")
    ).toBeInTheDocument()
  })
})
