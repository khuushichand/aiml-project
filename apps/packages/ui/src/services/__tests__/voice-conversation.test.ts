import { describe, expect, it, vi } from "vitest"

import {
  buildVoiceConversationPreflight,
  normalizeVoiceConversationRuntimeError,
  resolveVoiceConversationAvailability,
  resolveVoiceConversationTtsConfig
} from "@/services/tldw/voice-conversation"

describe("voice conversation contract", () => {
  it("keeps voice conversation unavailable when only broad audio flags exist", () => {
    const result = resolveVoiceConversationAvailability({
      isConnectionReady: true,
      hasVoiceConversationTransport: false,
      authReady: true,
      sttHealthState: "healthy",
      ttsHealthState: "healthy",
      selectedModel: "gpt-4o-mini",
      allowBackendDefaultModel: false,
      ttsConfigReady: true
    })

    expect(result.available).toBe(false)
    expect(result.reason).toBe("transport_missing")
  })

  it("maps browser TTS to server-backed tldw settings for voice conversation", () => {
    const result = resolveVoiceConversationTtsConfig({
      ttsProvider: "browser",
      tldwTtsModel: "kokoro",
      tldwTtsVoice: "af_heart",
      tldwTtsSpeed: 1.25,
      tldwTtsResponseFormat: "mp3",
      openAITTSModel: "tts-1",
      openAITTSVoice: "alloy",
      elevenLabsModel: "",
      elevenLabsVoiceId: "",
      speechPlaybackSpeed: 1,
      voiceChatTtsMode: "stream"
    })

    expect(result.ok).toBe(true)
    expect(result.value?.model).toBe("kokoro")
    expect(result.value?.voice).toBe("af_heart")
    expect(result.value?.speed).toBe(1.25)
    expect(result.value?.format).toBe("mp3")
    expect(result.value?.provider).toBeUndefined()
  })

  it("preserves explicit tldw provider on the voice conversation wire shape", () => {
    const result = resolveVoiceConversationTtsConfig({
      ttsProvider: "tldw",
      tldwTtsModel: "kokoro",
      tldwTtsVoice: "af_heart",
      tldwTtsSpeed: 1.25,
      tldwTtsResponseFormat: "mp3",
      openAITTSModel: "tts-1",
      openAITTSVoice: "alloy",
      elevenLabsModel: "",
      elevenLabsVoiceId: "",
      speechPlaybackSpeed: 1,
      voiceChatTtsMode: "stream"
    })

    expect(result.ok).toBe(true)
    expect(result.value?.model).toBe("kokoro")
    expect(result.value?.voice).toBe("af_heart")
    expect(result.value?.speed).toBe(1.25)
    expect(result.value?.format).toBe("mp3")
    expect(result.value?.provider).toBe("tldw")
  })

  it("rejects voice conversation availability when STT health is unhealthy", () => {
    const result = resolveVoiceConversationAvailability({
      isConnectionReady: true,
      hasVoiceConversationTransport: true,
      authReady: true,
      sttHealthState: "unhealthy",
      ttsHealthState: "healthy",
      selectedModel: "gpt-4o-mini",
      allowBackendDefaultModel: false,
      ttsConfigReady: true
    })

    expect(result.available).toBe(false)
    expect(result.reason).toBe("audio_unhealthy")
  })

  it("requires explicit OpenAI TTS model and voice when openai is selected", () => {
    const result = resolveVoiceConversationTtsConfig({
      ttsProvider: "openai",
      tldwTtsModel: "kokoro",
      tldwTtsVoice: "af_heart",
      tldwTtsSpeed: 1,
      tldwTtsResponseFormat: "mp3",
      openAITTSModel: "",
      openAITTSVoice: "",
      elevenLabsModel: "",
      elevenLabsVoiceId: "",
      speechPlaybackSpeed: 1,
      voiceChatTtsMode: "stream"
    })

    expect(result.ok).toBe(false)
    expect(result.reason).toBe("tts_config_missing")
  })

  it("requires explicit ElevenLabs model and voice id when elevenlabs is selected", () => {
    const result = resolveVoiceConversationTtsConfig({
      ttsProvider: "elevenlabs",
      tldwTtsModel: "kokoro",
      tldwTtsVoice: "af_heart",
      tldwTtsSpeed: 1,
      tldwTtsResponseFormat: "mp3",
      openAITTSModel: "tts-1",
      openAITTSVoice: "alloy",
      elevenLabsModel: "",
      elevenLabsVoiceId: "",
      speechPlaybackSpeed: 1,
      voiceChatTtsMode: "stream"
    })

    expect(result.ok).toBe(false)
    expect(result.reason).toBe("tts_config_missing")
  })

  it("builds preflight with backend defaults when no model is requested", async () => {
    const resolveProvider = vi.fn(async ({ modelId }: { modelId: string }) => `provider:${modelId}`)

    const result = await buildVoiceConversationPreflight({
      serverUrl: "http://127.0.0.1:8000/",
      token: "secret-token",
      requestedModel: "   ",
      ttsProvider: "browser",
      tldwTtsModel: "kokoro",
      tldwTtsVoice: "af_heart",
      tldwTtsSpeed: 1,
      tldwTtsResponseFormat: "pcm",
      openAITTSModel: "tts-1",
      openAITTSVoice: "alloy",
      elevenLabsModel: "",
      elevenLabsVoiceId: "",
      speechPlaybackSpeed: 1,
      voiceChatTtsMode: "stream",
      resolveProvider
    })

    expect(result.websocketUrl).toBe(
      "ws://127.0.0.1:8000/api/v1/audio/chat/stream?token=secret-token"
    )
    expect(result.llm).toEqual({})
    expect(result.tts).toEqual({
      model: "kokoro",
      voice: "af_heart",
      speed: 1,
      format: "mp3"
    })
    expect(resolveProvider).not.toHaveBeenCalled()
  })

  it("builds preflight with an explicit llm provider when a model is requested", async () => {
    const resolveProvider = vi.fn(async ({ modelId }: { modelId: string }) => `provider:${modelId}`)

    const result = await buildVoiceConversationPreflight({
      serverUrl: "http://127.0.0.1:8000",
      token: "abc123",
      requestedModel: "gpt-4o-mini",
      ttsProvider: "openai",
      tldwTtsModel: "kokoro",
      tldwTtsVoice: "af_heart",
      tldwTtsSpeed: 1,
      tldwTtsResponseFormat: "mp3",
      openAITTSModel: "tts-1",
      openAITTSVoice: "alloy",
      elevenLabsModel: "",
      elevenLabsVoiceId: "",
      speechPlaybackSpeed: 1.5,
      voiceChatTtsMode: "stream",
      resolveProvider
    })

    expect(result.llm).toEqual({
      model: "gpt-4o-mini",
      provider: "provider:gpt-4o-mini"
    })
    expect(result.tts).toEqual({
      provider: "openai",
      model: "tts-1",
      voice: "alloy",
      speed: 1.5,
      format: "mp3"
    })
    expect(resolveProvider).toHaveBeenCalledWith({ modelId: "gpt-4o-mini" })
  })

  it("normalizes disconnect-like runtime errors to a stable disconnected reason", () => {
    expect(normalizeVoiceConversationRuntimeError("websocket disconnected")).toEqual({
      reason: "voice_chat_disconnected",
      message: "Voice chat disconnected"
    })
  })

  it("normalizes TTS-like runtime errors to a stable TTS reason", () => {
    expect(
      normalizeVoiceConversationRuntimeError(new Error("TTS provider failed during synthesis"))
    ).toEqual({
      reason: "voice_chat_tts_error",
      message: "TTS provider failed during synthesis"
    })
  })
})
