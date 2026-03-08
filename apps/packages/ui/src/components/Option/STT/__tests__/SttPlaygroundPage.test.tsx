// @vitest-environment jsdom

import React from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"

const storageValues: Record<string, unknown> = {
  speechToTextLanguage: "fr",
  sttTask: "translate",
  sttResponseFormat: "verbose_json",
  sttTemperature: 0.4,
  sttPrompt: "Global prompt",
  sttUseSegmentation: true,
  sttSegK: 8,
  sttSegMinSegmentSize: 7,
  sttSegLambdaBalance: 0.2,
  sttSegUtteranceExpansionWidth: 3,
  sttSegEmbeddingsProvider: "openai",
  sttSegEmbeddingsModel: "text-embedding-3-small",
  sttComparisonHistory: []
}

let comparisonPanelProps: Record<string, unknown> | null = null

// Mock all dependencies before importing the component
vi.mock("@plasmohq/storage/hook", () => ({
  useStorage: (key: string, defaultVal: unknown) => [
    key in storageValues ? storageValues[key] : defaultVal,
    vi.fn()
  ]
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (_k: string, f: string) => f })
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    getTranscriptionModels: vi
      .fn()
      .mockResolvedValue({ all_models: ["whisper-1", "distil-v3"] }),
    transcribeAudio: vi.fn().mockResolvedValue({ text: "test" }),
    createNote: vi.fn().mockResolvedValue({})
  }
}))

vi.mock("@/components/Common/PageShell", () => ({
  PageShell: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="page-shell">{children}</div>
  )
}))

vi.mock("@/hooks/useAntdNotification", () => ({
  useAntdNotification: () => ({
    error: vi.fn(),
    success: vi.fn(),
    info: vi.fn()
  })
}))

vi.mock("@/utils/request-timeout", () => ({
  isTimeoutLikeError: () => false
}))

// Mock the sub-components to keep tests focused
vi.mock("../RecordingStrip", () => ({
  RecordingStrip: (_props: Record<string, unknown>) => (
    <div data-testid="recording-strip" />
  )
}))

vi.mock("../InlineSettingsPanel", () => ({
  InlineSettingsPanel: (_props: Record<string, unknown>) => (
    <div data-testid="settings-panel" />
  )
}))

vi.mock("../ComparisonPanel", () => ({
  ComparisonPanel: (props: Record<string, unknown>) => {
    comparisonPanelProps = props
    return <div data-testid="comparison-panel" />
  }
}))

vi.mock("../HistoryPanel", () => ({
  HistoryPanel: (_props: Record<string, unknown>) => (
    <div data-testid="history-panel" />
  )
}))

vi.mock("@/db/dexie/stt-recordings", () => ({
  saveSttRecording: vi.fn().mockResolvedValue("rec-1"),
  getSttRecording: vi.fn(),
  deleteSttRecording: vi.fn()
}))

import { SttPlaygroundPage } from "../SttPlaygroundPage"

describe("SttPlaygroundPage", () => {
  beforeEach(() => {
    comparisonPanelProps = null
  })

  it("renders page title 'STT Playground'", () => {
    render(<SttPlaygroundPage />)
    expect(screen.getByText("STT Playground")).toBeTruthy()
  })

  it("renders all 3 zones (recording-strip, comparison-panel, history-panel)", () => {
    render(<SttPlaygroundPage />)
    expect(screen.getByTestId("recording-strip")).toBeTruthy()
    expect(screen.getByTestId("comparison-panel")).toBeTruthy()
    expect(screen.getByTestId("history-panel")).toBeTruthy()
  })

  it("settings panel is hidden by default", () => {
    render(<SttPlaygroundPage />)
    expect(screen.queryByTestId("settings-panel")).toBeNull()
  })

  it("applies global STT defaults even before opening settings", () => {
    render(<SttPlaygroundPage />)

    expect(comparisonPanelProps?.sttOptions).toEqual({
      language: "fr",
      task: "translate",
      response_format: "verbose_json",
      temperature: 0.4,
      prompt: "Global prompt",
      segment: true,
      seg_K: 8,
      seg_min_segment_size: 7,
      seg_lambda_balance: 0.2,
      seg_utterance_expansion_width: 3,
      seg_embeddings_provider: "openai",
      seg_embeddings_model: "text-embedding-3-small"
    })
  })
})
