import { act, renderHook } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { useVoiceChatStream } from "@/hooks/useVoiceChatStream"

const micState = vi.hoisted(() => ({
  callback: null as ((chunk: ArrayBuffer) => void) | null,
  start: vi.fn(async () => {}),
  stop: vi.fn(() => {}),
  active: true
}))

const audioPlayerState = vi.hoisted(() => ({
  start: vi.fn(() => {}),
  append: vi.fn(() => {}),
  finish: vi.fn(() => {}),
  stop: vi.fn(() => {}),
  state: { playing: false }
}))

vi.mock("@/hooks/useMicStream", () => ({
  useMicStream: (cb: (chunk: ArrayBuffer) => void) => {
    micState.callback = cb
    return {
      start: micState.start,
      stop: micState.stop,
      active: micState.active
    }
  }
}))

vi.mock("@/hooks/useStreamingAudioPlayer", () => ({
  useStreamingAudioPlayer: () => ({
    start: audioPlayerState.start,
    append: audioPlayerState.append,
    finish: audioPlayerState.finish,
    stop: audioPlayerState.stop,
    state: audioPlayerState.state
  })
}))

vi.mock("@/hooks/useVoiceChatSettings", () => ({
  useVoiceChatSettings: () => ({
    voiceChatModel: "test-model",
    voiceChatPauseMs: 700,
    voiceChatTriggerPhrases: [],
    voiceChatAutoResume: true,
    voiceChatBargeIn: true,
    voiceChatTtsMode: "stream"
  })
}))

vi.mock("@/hooks/useSttSettings", () => ({
  useSttSettings: () => ({
    model: "parakeet",
    temperature: 0,
    task: "transcribe",
    responseFormat: "json",
    timestampGranularities: "word",
    prompt: "",
    useSegmentation: false,
    segK: 2,
    segMinSegmentSize: 20,
    segLambdaBalance: 0.5,
    segUtteranceExpansionWidth: 2,
    segEmbeddingsProvider: "",
    segEmbeddingsModel: ""
  })
}))

vi.mock("@/utils/resolve-api-provider", () => ({
  resolveApiProviderForModel: vi.fn(async () => "stub")
}))

vi.mock("@plasmohq/storage/hook", () => ({
  useStorage: (key: string, defaultValue: unknown) => {
    const map: Record<string, unknown> = {
      speechToTextLanguage: "en-US",
      selectedModel: "test-model",
      ttsProvider: "tldw",
      tldwTtsModel: "kokoro",
      tldwTtsVoice: "af_heart",
      tldwTtsResponseFormat: "mp3",
      tldwTtsSpeed: 1,
      openAITTSModel: "tts-1",
      openAITTSVoice: "alloy",
      elevenLabsModel: "",
      elevenLabsVoiceId: "",
      speechPlaybackSpeed: 1
    }
    return [map[key] ?? defaultValue]
  }
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    getConfig: vi.fn(async () => ({
      serverUrl: "http://localhost:8000",
      authMode: "single_user",
      apiKey: "test-key"
    }))
  }
}))

class MockWebSocket {
  static OPEN = 1
  static CLOSED = 3
  static instances: MockWebSocket[] = []

  readyState = 0
  binaryType = "blob"
  sent: string[] = []
  onopen: (() => void) | null = null
  onmessage: ((event: { data: string | ArrayBuffer }) => void) | null = null
  onerror: (() => void) | null = null
  onclose: (() => void) | null = null
  url: string

  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }

  send(payload: string) {
    this.sent.push(payload)
  }

  close() {
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.()
  }

  triggerOpen() {
    this.readyState = MockWebSocket.OPEN
    this.onopen?.()
  }

  triggerJson(payload: unknown) {
    this.onmessage?.({ data: JSON.stringify(payload) })
  }
}

describe("useVoiceChatStream interrupt handling", () => {
  beforeEach(() => {
    MockWebSocket.instances = []
    micState.callback = null
    micState.start.mockClear()
    micState.stop.mockClear()
    audioPlayerState.start.mockClear()
    audioPlayerState.append.mockClear()
    audioPlayerState.finish.mockClear()
    audioPlayerState.stop.mockClear()
    ;(globalThis as any).WebSocket = MockWebSocket
  })

  it("sends interrupt when barge-in audio resumes while speaking", async () => {
    renderHook(() =>
      useVoiceChatStream({
        active: true
      })
    )

    await act(async () => {
      await Promise.resolve()
      await Promise.resolve()
    })

    const ws = MockWebSocket.instances[0]
    expect(ws).toBeDefined()

    await act(async () => {
      ws.triggerOpen()
      await Promise.resolve()
    })

    await act(async () => {
      ws.triggerJson({ type: "tts_start", format: "mp3" })
      await Promise.resolve()
    })

    const priorSendCount = ws.sent.length
    await act(async () => {
      micState.callback?.(new ArrayBuffer(8))
      await Promise.resolve()
    })

    const newFrames = ws.sent.slice(priorSendCount).map((raw) => JSON.parse(raw))
    expect(newFrames[0]?.type).toBe("interrupt")
  })

  it("returns to listening when interrupted frame arrives", async () => {
    const onStateChange = vi.fn()
    renderHook(() =>
      useVoiceChatStream({
        active: true,
        onStateChange
      })
    )

    await act(async () => {
      await Promise.resolve()
      await Promise.resolve()
    })

    const ws = MockWebSocket.instances[0]
    expect(ws).toBeDefined()

    await act(async () => {
      ws.triggerOpen()
      await Promise.resolve()
    })

    await act(async () => {
      ws.triggerJson({ type: "tts_start", format: "mp3" })
      await Promise.resolve()
    })
    expect(onStateChange).toHaveBeenCalledWith("speaking")

    await act(async () => {
      ws.triggerJson({ type: "interrupted", phase: "both" })
      await Promise.resolve()
    })

    expect(onStateChange).toHaveBeenLastCalledWith("listening")
  })
})
