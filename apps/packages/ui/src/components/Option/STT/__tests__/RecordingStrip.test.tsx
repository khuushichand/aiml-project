import React from "react"
import { render, screen, fireEvent } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mockStartRecording = vi.fn()
const mockStopRecording = vi.fn()
const mockClearRecording = vi.fn()
const mockLoadBlob = vi.fn()

vi.mock("@/hooks/useAudioRecorder", () => ({
  useAudioRecorder: () => ({
    status: "idle",
    blob: null,
    durationMs: 0,
    startRecording: mockStartRecording,
    stopRecording: mockStopRecording,
    clearRecording: mockClearRecording,
    loadBlob: mockLoadBlob
  })
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, fallback: string) => fallback
  })
}))

vi.mock("@/hooks/useAntdNotification", () => ({
  useAntdNotification: () => ({
    error: vi.fn(),
    success: vi.fn()
  })
}))

import { RecordingStrip } from "../RecordingStrip"

describe("RecordingStrip", () => {
  const mockOnBlobReady = vi.fn()
  const mockOnSettingsToggle = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders record button in idle state", () => {
    render(<RecordingStrip onBlobReady={mockOnBlobReady} />)
    const btn = screen.getByRole("button", { name: /start recording/i })
    expect(btn).toBeInTheDocument()
  })

  it("calls startRecording when record clicked", () => {
    render(<RecordingStrip onBlobReady={mockOnBlobReady} />)
    const btn = screen.getByRole("button", { name: /start recording/i })
    fireEvent.click(btn)
    expect(mockStartRecording).toHaveBeenCalledOnce()
  })

  it("shows upload button", () => {
    render(<RecordingStrip onBlobReady={mockOnBlobReady} />)
    const uploadBtn = screen.getByRole("button", { name: "Upload audio file" })
    expect(uploadBtn).toBeInTheDocument()
  })

  it("shows settings toggle button when prop provided", () => {
    render(
      <RecordingStrip
        onBlobReady={mockOnBlobReady}
        onSettingsToggle={mockOnSettingsToggle}
      />
    )
    const settingsBtn = screen.getByRole("button", { name: "Toggle settings" })
    expect(settingsBtn).toBeInTheDocument()
    fireEvent.click(settingsBtn)
    expect(mockOnSettingsToggle).toHaveBeenCalledOnce()
  })

  it("has correct aria-label on record button", () => {
    render(<RecordingStrip onBlobReady={mockOnBlobReady} />)
    const btn = screen.getByRole("button", { name: /start recording/i })
    expect(btn.getAttribute("aria-label")).toContain("Start recording")
  })
})
