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
    render(
      <AssistantDefaultsPanel
        selectedPersonaId="persona-1"
        selectedPersonaName="Helper"
        isActive
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
})
