import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"

const mockStartRecording = vi.fn().mockResolvedValue(undefined)
const mockStopRecording = vi.fn()

vi.mock("@/hooks/useAudioRecorder", () => ({
  useAudioRecorder: () => ({
    status: "idle",
    blob: null,
    durationMs: 0,
    startRecording: mockStartRecording,
    stopRecording: mockStopRecording,
    clearRecording: vi.fn(),
    loadBlob: vi.fn()
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

describe("keyboard shortcuts", () => {
  beforeEach(() => vi.clearAllMocks())

  it("starts recording on stt-toggle-record custom event", () => {
    render(<RecordingStrip onBlobReady={vi.fn()} />)
    window.dispatchEvent(new CustomEvent("stt-toggle-record"))
    expect(mockStartRecording).toHaveBeenCalled()
  })

  it("record button aria-label includes Space shortcut hint", () => {
    render(<RecordingStrip onBlobReady={vi.fn()} />)
    const btn = screen.getByRole("button", { name: /start recording/i })
    expect(btn.getAttribute("aria-label")).toContain("Space")
  })
})
