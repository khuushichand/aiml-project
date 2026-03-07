import React from "react"
import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"

// Mock all dependencies before importing the component
vi.mock("@plasmohq/storage/hook", () => ({
  useStorage: (_key: string, defaultVal: unknown) => [defaultVal, vi.fn()]
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
  ComparisonPanel: (_props: Record<string, unknown>) => (
    <div data-testid="comparison-panel" />
  )
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
})
