import { act, renderHook, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { useVoiceChatStream } from "@/hooks/useVoiceChatStream"

const micState = vi.hoisted(() => ({
  callback: null as ((chunk: ArrayBuffer) => void) | null,
  start: vi.fn(async () => {}),
  stop: vi.fn(() => {}),
  active: true
}))

const { storageValues, useStorageMock } = vi.hoisted(() => ({
  storageValues: new Map<string, unknown>(),
  useStorageMock: vi.fn()
}))

const audioCatalogState = vi.hoisted(() => ({
  devices: [] as Array<{ deviceId: string; label: string }>,
  isSettled: true
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

vi.mock("@/hooks/useAudioSourceCatalog", () => ({
  useAudioSourceCatalog: () => audioCatalogState
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
  useStorage: useStorageMock
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
  const originalDeploymentMode = process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE
  const originalWindow = globalThis.window

  beforeEach(() => {
    MockWebSocket.instances = []
    micState.callback = null
    micState.start.mockClear()
    micState.stop.mockClear()
    audioPlayerState.start.mockClear()
    audioPlayerState.append.mockClear()
    audioPlayerState.finish.mockClear()
    audioPlayerState.stop.mockClear()
    audioCatalogState.devices = [
      { deviceId: "default", label: "Default microphone" },
      { deviceId: "usb-1", label: "USB microphone" }
    ]
    audioCatalogState.isSettled = true
    storageValues.clear()
    storageValues.set("speechToTextLanguage", "en-US")
    storageValues.set("selectedModel", "test-model")
    storageValues.set("ttsProvider", "tldw")
    storageValues.set("tldwTtsModel", "kokoro")
    storageValues.set("tldwTtsVoice", "af_heart")
    storageValues.set("tldwTtsResponseFormat", "mp3")
    storageValues.set("tldwTtsSpeed", 1)
    storageValues.set("openAITTSModel", "tts-1")
    storageValues.set("openAITTSVoice", "alloy")
    storageValues.set("elevenLabsModel", "")
    storageValues.set("elevenLabsVoiceId", "")
    storageValues.set("speechPlaybackSpeed", 1)
    delete process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE
    useStorageMock.mockReset()
    useStorageMock.mockImplementation((key: string, defaultValue: unknown) => [
      storageValues.has(key) ? storageValues.get(key) : defaultValue,
      vi.fn(),
      { isLoading: key === "liveVoiceAudioSourcePreference" ? false : false }
    ])
    ;(globalThis as any).WebSocket = MockWebSocket
    const mockWindow = Object.create(originalWindow)
    Object.defineProperty(mockWindow, "location", {
      value: {
        origin: "http://127.0.0.1:8080",
        protocol: "http:"
      },
      configurable: true
    })
    Object.defineProperty(globalThis, "window", {
      value: mockWindow,
      configurable: true
    })
  })

  afterEach(() => {
    if (originalDeploymentMode === undefined) {
      delete process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE
    } else {
      process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE = originalDeploymentMode
    }
    Object.defineProperty(globalThis, "window", {
      value: originalWindow,
      configurable: true
    })
  })

  it("uses the webui origin for quickstart voice chat websocket urls", async () => {
    process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE = "quickstart"

    renderHook(() =>
      useVoiceChatStream({
        active: true
      })
    )

    await act(async () => {
      await Promise.resolve()
      await Promise.resolve()
    })

    expect(MockWebSocket.instances[0]?.url).toBe(
      "ws://127.0.0.1:8080/api/v1/audio/chat/stream?token=test-key"
    )
  })

  it("starts live voice with the remembered live_voice mic device", async () => {
    storageValues.set("liveVoiceAudioSourcePreference", {
      featureGroup: "live_voice",
      sourceKind: "mic_device",
      deviceId: "usb-1",
      lastKnownLabel: "USB microphone"
    })

    const { result } = renderHook(() =>
      useVoiceChatStream({
        active: false
      })
    )

    await act(async () => {
      await result.current.start()
      await Promise.resolve()
      await Promise.resolve()
    })

    const ws = MockWebSocket.instances[0]
    expect(ws).toBeDefined()

    await act(async () => {
      ws.triggerOpen()
      await Promise.resolve()
      await Promise.resolve()
    })

    expect(micState.start).toHaveBeenCalledWith({ deviceId: "usb-1" })
  })

  it("waits for the live_voice preference to hydrate before starting", async () => {
    storageValues.set("liveVoiceAudioSourcePreference", {
      featureGroup: "live_voice",
      sourceKind: "mic_device",
      deviceId: "usb-1",
      lastKnownLabel: "USB microphone"
    })

    let preferenceLoading = true
    useStorageMock.mockImplementation((key: string, defaultValue: unknown) => [
      storageValues.has(key) ? storageValues.get(key) : defaultValue,
      vi.fn(),
      { isLoading: key === "liveVoiceAudioSourcePreference" ? preferenceLoading : false }
    ])

    const { rerender } = renderHook(() =>
      useVoiceChatStream({
        active: true
      })
    )

    expect(MockWebSocket.instances).toHaveLength(0)
    expect(micState.start).not.toHaveBeenCalled()

    await act(async () => {
      preferenceLoading = false
      rerender()
      await Promise.resolve()
      await Promise.resolve()
    })

    const ws = MockWebSocket.instances[0]
    expect(ws).toBeDefined()

    await act(async () => {
      ws.triggerOpen()
      await Promise.resolve()
      await Promise.resolve()
    })

    await waitFor(() => {
      expect(micState.start).toHaveBeenCalledWith({ deviceId: "usb-1" })
    })
  })

  it("falls back to the default microphone when the remembered live_voice device is missing", async () => {
    storageValues.set("liveVoiceAudioSourcePreference", {
      featureGroup: "live_voice",
      sourceKind: "mic_device",
      deviceId: "usb-missing",
      lastKnownLabel: "Studio microphone"
    })
    audioCatalogState.devices = [{ deviceId: "default", label: "Default microphone" }]

    const { result } = renderHook(() =>
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
      await Promise.resolve()
    })

    expect(micState.start).toHaveBeenCalledWith({ deviceId: null })
    expect(result.current.connected).toBe(true)
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
