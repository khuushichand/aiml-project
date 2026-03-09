// @vitest-environment jsdom

import React from "react"
import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

type QueryOptions = {
  queryKey?: readonly unknown[]
}

const { invalidateQueriesMock, transcribeAudioMock, getTranscriptionModelsMock } =
  vi.hoisted(() => ({
    invalidateQueriesMock: vi.fn(),
    transcribeAudioMock: vi.fn(),
    getTranscriptionModelsMock: vi.fn(async () => ({
      all_models: ["whisper-1"],
    })),
  }))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback || _key,
  }),
}))

vi.mock("@plasmohq/storage/hook", () => ({
  useStorage: (_key: string, defaultValue: unknown) =>
    [defaultValue, vi.fn(), { isLoading: false }] as const,
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
  })

  it("renders without triggering a temporal dead zone error", (): void => {
    render(<SpeechPlaygroundPage />)

    expect(screen.getByTestId("speech-page-shell")).toBeInTheDocument()
  })
})
