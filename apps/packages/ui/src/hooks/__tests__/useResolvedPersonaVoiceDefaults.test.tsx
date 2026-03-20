import { renderHook } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const storageState = vi.hoisted(() => ({
  values: {
    speechToTextLanguage: "en-US",
    ttsProvider: "tldw",
    tldwTtsVoice: "af_heart",
    openAITTSVoice: "alloy",
    elevenLabsVoiceId: "voice-eleven"
  } as Record<string, unknown>
}))

const voiceChatState = vi.hoisted(() => ({
  voiceChatTriggerPhrases: ["hey assistant"],
  voiceChatAutoResume: true,
  voiceChatBargeIn: false
}))

const sttState = vi.hoisted(() => ({
  model: "parakeet"
}))

vi.mock("@plasmohq/storage/hook", () => ({
  useStorage: (key: string, defaultValue: unknown) => [
    key in storageState.values ? storageState.values[key] : defaultValue
  ]
}))

vi.mock("@/hooks/useVoiceChatSettings", () => ({
  useVoiceChatSettings: () => voiceChatState
}))

vi.mock("@/hooks/useSttSettings", () => ({
  useSttSettings: () => ({
    model: sttState.model,
    temperature: 0,
    task: "transcribe",
    responseFormat: "json",
    timestampGranularities: "segment",
    prompt: "",
    useSegmentation: false,
    segK: 3,
    segMinSegmentSize: 20,
    segLambdaBalance: 0.5,
    segUtteranceExpansionWidth: 2,
    segEmbeddingsProvider: "",
    segEmbeddingsModel: ""
  })
}))

import { useResolvedPersonaVoiceDefaults } from "../useResolvedPersonaVoiceDefaults"

describe("useResolvedPersonaVoiceDefaults", () => {
  beforeEach(() => {
    storageState.values = {
      speechToTextLanguage: "en-US",
      ttsProvider: "tldw",
      tldwTtsVoice: "af_heart",
      openAITTSVoice: "alloy",
      elevenLabsVoiceId: "voice-eleven"
    }
    voiceChatState.voiceChatTriggerPhrases = ["hey assistant"]
    voiceChatState.voiceChatAutoResume = true
    voiceChatState.voiceChatBargeIn = false
    sttState.model = "parakeet"
  })

  it("prefers persona defaults and falls back to browser values for missing fields", () => {
    const { result } = renderHook(() =>
      useResolvedPersonaVoiceDefaults({
        stt_language: "fr-FR",
        tts_provider: "openai",
        confirmation_mode: "always",
        voice_chat_trigger_phrases: ["bonjour helper"],
        auto_resume: false,
        auto_commit_enabled: false,
        vad_threshold: 0.61,
        min_silence_ms: 640,
        turn_stop_secs: 0.48,
        min_utterance_secs: 0.82
      })
    )

    expect(result.current).toEqual({
      sttLanguage: "fr-FR",
      sttModel: "parakeet",
      ttsProvider: "openai",
      ttsVoice: "alloy",
      confirmationMode: "always",
      voiceChatTriggerPhrases: ["bonjour helper"],
      autoResume: false,
      bargeIn: false,
      autoCommitEnabled: false,
      vadThreshold: 0.61,
      minSilenceMs: 640,
      turnStopSecs: 0.48,
      minUtteranceSecs: 0.82
    })
  })

  it("uses browser-backed defaults when persona values are absent", () => {
    storageState.values.ttsProvider = "elevenlabs"
    voiceChatState.voiceChatTriggerPhrases = ["okay helper", "status check"]
    voiceChatState.voiceChatAutoResume = false
    voiceChatState.voiceChatBargeIn = true
    sttState.model = "whisper-1"

    const { result } = renderHook(() => useResolvedPersonaVoiceDefaults(null))

    expect(result.current).toEqual({
      sttLanguage: "en-US",
      sttModel: "whisper-1",
      ttsProvider: "elevenlabs",
      ttsVoice: "voice-eleven",
      confirmationMode: "destructive_only",
      voiceChatTriggerPhrases: ["okay helper", "status check"],
      autoResume: false,
      bargeIn: true,
      autoCommitEnabled: true,
      vadThreshold: 0.5,
      minSilenceMs: 250,
      turnStopSecs: 0.2,
      minUtteranceSecs: 0.4
    })
  })
})
