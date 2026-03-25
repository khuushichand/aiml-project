// @vitest-environment jsdom

import React from "react"
import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

type QueryOptions = {
  queryKey?: readonly unknown[]
}

const updateStoredValue = (
  storageValues: Map<string, unknown>,
  key: string,
  defaultValue: unknown,
  nextValue: unknown
) => {
  const currentValue = storageValues.has(key)
    ? storageValues.get(key)
    : defaultValue
  const resolvedValue =
    typeof nextValue === "function"
      ? (nextValue as (current: unknown) => unknown)(currentValue)
      : nextValue
  storageValues.set(key, resolvedValue)
}

const { invalidateQueriesMock, transcribeAudioMock, getTranscriptionModelsMock } =
  vi.hoisted(() => ({
    invalidateQueriesMock: vi.fn(),
    transcribeAudioMock: vi.fn(),
    getTranscriptionModelsMock: vi.fn(async () => ({
      all_models: ["whisper-1"],
    })),
  }))

const { storageValues, setSpeechModeMock, setSpeechHistoryMock } = vi.hoisted(() => ({
  storageValues: new Map<string, unknown>(),
  setSpeechModeMock: vi.fn(),
  setSpeechHistoryMock: vi.fn(),
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback || _key,
  }),
}))

vi.mock("@plasmohq/storage/hook", () => ({
  useStorage: (key: string, defaultValue: unknown) => {
    if (key === "speechPlaygroundMode") {
      return [
        storageValues.has(key) ? storageValues.get(key) : defaultValue,
        (nextValue: unknown) => {
          setSpeechModeMock(nextValue)
          updateStoredValue(storageValues, key, defaultValue, nextValue)
        },
        { isLoading: false }
      ] as const
    }
    if (key === "speechPlaygroundHistory") {
      return [
        storageValues.has(key) ? storageValues.get(key) : defaultValue,
        (nextValue: unknown) => {
          setSpeechHistoryMock(nextValue)
          updateStoredValue(storageValues, key, defaultValue, nextValue)
        },
        { isLoading: false }
      ] as const
    }
    return [
      storageValues.has(key) ? storageValues.get(key) : defaultValue,
      (nextValue: unknown) =>
        updateStoredValue(storageValues, key, defaultValue, nextValue),
      { isLoading: false }
    ] as const
  },
}))

vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({
    invalidateQueries: invalidateQueriesMock,
  }),
  useQuery: vi.fn((options: QueryOptions | undefined) => {
    if (options?.queryKey?.[0] === "fetchTTSSettings") {
      return {
        data: {
          ttsProvider: "browser",
          ttsEnabled: true,
          tldwTtsSpeed: 1,
          tldwTtsStreaming: false,
          responseSplitting: "punctuation",
        },
        isLoading: false,
      }
    }
    return {
      data: [],
      isLoading: false,
    }
  }),
}))

vi.mock("@/components/Common/PageShell", () => ({
  PageShell: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="speech-page-shell">{children}</div>
  ),
}))

vi.mock("@/components/Common/WaveformCanvas", () => ({
  default: () => <div data-testid="waveform-canvas" />,
}))

vi.mock("@/components/Common/TtsJobProgress", () => ({
  TtsJobProgress: () => <div data-testid="tts-job-progress" />,
}))

vi.mock("@/components/Common/LongformDraftEditor", () => ({
  LongformDraftEditor: () => <div data-testid="longform-draft-editor" />,
}))

vi.mock("@/components/Common/CharacterProgressBar", () => ({
  CharacterProgressBar: () => <div data-testid="character-progress-bar" />,
}))

vi.mock("@/components/Option/Speech/TtsProviderStrip", () => ({
  TtsProviderStrip: () => <div data-testid="tts-provider-strip" />,
}))

vi.mock("@/components/Option/Speech/TtsStickyActionBar", () => ({
  TtsStickyActionBar: () => <div data-testid="tts-sticky-action-bar" />,
}))

vi.mock("@/components/Option/Speech/TtsInspectorPanel", () => ({
  TtsInspectorPanel: () => <div data-testid="tts-inspector-panel" />,
}))

vi.mock("@/components/Option/Speech/TtsVoiceTab", () => ({
  TtsVoiceTab: () => <div data-testid="tts-voice-tab" />,
}))

vi.mock("@/components/Option/Speech/TtsOutputTab", () => ({
  TtsOutputTab: () => <div data-testid="tts-output-tab" />,
}))

vi.mock("@/components/Option/Speech/TtsAdvancedTab", () => ({
  TtsAdvancedTab: () => <div data-testid="tts-advanced-tab" />,
}))

vi.mock("@/components/Option/TTS/VoiceCloningManager", () => ({
  VoiceCloningManager: () => <div data-testid="voice-cloning-manager" />,
}))

vi.mock("@/components/Option/Speech/RenderStrip", () => ({
  RenderStrip: () => <div data-testid="render-strip" />,
}))

vi.mock("@/components/Option/Speech/VoicePickerModal", () => ({
  VoicePickerModal: () => <div data-testid="voice-picker-modal" />,
}))

vi.mock("@/hooks/useTtsPlayground", () => ({
  TTS_PRESETS: {
    balanced: {
      label: "Balanced",
      value: "balanced",
    },
  },
  useTtsPlayground: () => ({
    segments: [],
    isGenerating: false,
    generateSegments: vi.fn(async () => []),
    clearSegments: vi.fn(),
    setSegments: vi.fn(),
  }),
}))

vi.mock("@/hooks/useStreamingAudioPlayer", () => ({
  useStreamingAudioPlayer: () => ({
    start: vi.fn(),
    append: vi.fn(),
    finish: vi.fn(),
    stop: vi.fn(),
    state: "idle",
    getBufferedBlob: vi.fn(() => null),
  }),
}))

vi.mock("@/hooks/useTtsProviderData", () => ({
  OPENAI_TTS_MODELS: ["tts-1"],
  OPENAI_TTS_VOICES: {
    "tts-1": [{ label: "Alloy", value: "alloy" }],
  },
  useTtsProviderData: () => ({
    hasAudio: true,
    providersInfo: {
      providers: {
        browser: {
          supports_streaming: false,
        },
      },
      voices: {},
    },
    tldwTtsModels: [],
    tldwVoiceCatalog: [],
    elevenLabsData: null,
    elevenLabsLoading: false,
    elevenLabsError: null,
    refetchElevenLabs: vi.fn(),
  }),
}))

vi.mock("@/hooks/useMultiRenderState", () => ({
  useMultiRenderState: () => ({
    renders: [],
    hasReady: false,
    hasIdle: false,
    playingId: null,
    addRender: vi.fn(),
    updateConfig: vi.fn(),
    generateAll: vi.fn(async () => undefined),
    playAllSequentially: vi.fn(),
    clearAll: vi.fn(),
    generateRender: vi.fn(async () => undefined),
    removeRender: vi.fn(),
    startPlaying: vi.fn(),
    stopPlaying: vi.fn(),
    handleStripEnded: vi.fn(),
  }),
}))

vi.mock("@/services/tts-provider", () => ({
  inferTldwProviderFromModel: vi.fn(() => null),
  resolveTtsProviderContext: vi.fn(async (text: string) => ({
    utterance: text,
  })),
}))

vi.mock("@/services/tts-providers", () => ({
  getTtsProviderLabel: vi.fn((provider?: string) => provider || "browser"),
}))

vi.mock("@/services/tts", () => ({
  getTTSProvider: vi.fn(async () => "browser"),
  getTTSSettings: vi.fn(async () => ({
    ttsProvider: "browser",
    ttsEnabled: true,
    responseSplitting: "punctuation",
    tldwTtsSpeed: 1,
    tldwTtsStreaming: false,
  })),
  setTTSSettings: vi.fn(async () => undefined),
  SUPPORTED_TLDW_TTS_FORMATS: ["mp3"],
  setTldwTTSSpeed: vi.fn(),
  setTldwTTSResponseFormat: vi.fn(),
  setTldwTTSStreamingEnabled: vi.fn(),
  setResponseSplitting: vi.fn(),
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    getTranscriptionModels: getTranscriptionModelsMock,
    transcribeAudio: transcribeAudioMock,
    createNote: vi.fn(async () => undefined),
    getConfig: vi.fn(async () => ({
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single_user",
      apiKey: "test-key",
    })),
    createTtsJob: vi.fn(),
    streamAudioJobProgress: vi.fn(),
    getTtsJobArtifacts: vi.fn(),
    downloadOutput: vi.fn(),
  },
}))

vi.mock("@/utils/clipboard", () => ({
  copyToClipboard: vi.fn(async () => true),
}))

vi.mock("@/utils/tts", () => ({
  estimateTtsDurationSeconds: vi.fn(() => 1),
  splitMessageContent: vi.fn((text: string) => [text]),
}))

vi.mock("@/utils/markdown-to-text", () => ({
  markdownToText: vi.fn((text: string) => text),
}))

vi.mock("@/utils/request-timeout", () => ({
  isTimeoutLikeError: vi.fn(() => false),
}))

vi.mock("@/utils/template-guards", () => ({
  withTemplateFallback: vi.fn((_template: string, fallback: string) => fallback),
}))

vi.mock("@/services/tldw/voice-cloning", () => ({
  listCustomVoices: vi.fn(async () => []),
}))

vi.mock("@/services/tldw/tts-provider-keys", () => ({
  normalizeTtsProviderKey: vi.fn((value?: string) => value || ""),
  toServerTtsProviderKey: vi.fn((value?: string) => value || ""),
}))

import SpeechPlaygroundPage from "../SpeechPlaygroundPage"

describe("SpeechPlaygroundPage", () => {
  beforeEach((): void => {
    vi.clearAllMocks()
    invalidateQueriesMock.mockReset()
    transcribeAudioMock.mockReset()
    getTranscriptionModelsMock.mockClear()
    storageValues.clear()
    storageValues.set("speechPlaygroundMode", "roundtrip")
    storageValues.set("speechPlaygroundHistory", [])
    setSpeechModeMock.mockReset()
    setSpeechHistoryMock.mockReset()
  })

  it("renders without triggering a temporal dead zone error", (): void => {
    render(<SpeechPlaygroundPage />)

    expect(screen.getByTestId("speech-page-shell")).toBeInTheDocument()
  })

  it("hides the mode switcher and STT region when locked to listen mode", (): void => {
    storageValues.set("speechPlaygroundMode", "speak")

    render(<SpeechPlaygroundPage lockedMode="listen" hideModeSwitcher />)

    expect(screen.queryByText("Mode")).not.toBeInTheDocument()
    expect(screen.queryByText("Current transcription model")).not.toBeInTheDocument()
    expect(screen.getByTestId("tts-provider-strip")).toBeInTheDocument()
    expect(getTranscriptionModelsMock).not.toHaveBeenCalled()
  })

  it("uses TTS-specific page copy and history controls when locked to listen mode", (): void => {
    render(<SpeechPlaygroundPage lockedMode="listen" hideModeSwitcher />)

    expect(screen.getByText("TTS Playground")).toBeInTheDocument()
    expect(
      screen.getByText("Draft text, choose a voice, and generate audio in one place.")
    ).toBeInTheDocument()
    expect(screen.getByText("TTS history")).toBeInTheDocument()
    expect(screen.getByText("Generate audio to see TTS history here.")).toBeInTheDocument()
    expect(screen.queryByTestId("speech-history-type-filter")).not.toBeInTheDocument()
  })

  it("does not overwrite stored mode when locked mode is provided", (): void => {
    storageValues.set("speechPlaygroundMode", "speak")

    render(<SpeechPlaygroundPage lockedMode="listen" hideModeSwitcher />)

    expect(setSpeechModeMock).not.toHaveBeenCalled()
  })

  it("filters stored history down to TTS entries when locked to listen mode", (): void => {
    storageValues.set("speechPlaygroundHistory", [
      {
        id: "stt-1",
        type: "stt",
        createdAt: "2026-03-11T00:00:00.000Z",
        text: "Recorded transcript",
      },
      {
        id: "tts-1",
        type: "tts",
        createdAt: "2026-03-11T00:01:00.000Z",
        text: "Synthesized narration",
      },
    ])

    render(<SpeechPlaygroundPage lockedMode="listen" hideModeSwitcher />)

    expect(screen.getByText("Synthesized narration")).toBeInTheDocument()
    expect(screen.queryByText("Recorded transcript")).not.toBeInTheDocument()
  })

  it("keeps the mode switcher visible when unlocked", (): void => {
    render(<SpeechPlaygroundPage />)

    expect(screen.getByText("Speech Playground")).toBeInTheDocument()
    expect(screen.getByText("Mode")).toBeInTheDocument()
    expect(screen.getByTestId("speech-history-type-filter")).toBeInTheDocument()
    expect(getTranscriptionModelsMock).toHaveBeenCalled()
  })

  it("shows the shared audio source picker in the speech playground", (): void => {
    render(<SpeechPlaygroundPage />)

    expect(
      screen.getByLabelText("Speech playground input source")
    ).toBeInTheDocument()
  })
})
