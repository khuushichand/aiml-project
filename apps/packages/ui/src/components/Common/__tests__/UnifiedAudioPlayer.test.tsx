import React from "react"
import { describe, expect, it, vi, beforeEach } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"
import { UnifiedAudioPlayer } from "../UnifiedAudioPlayer"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback || _key
  })
}))

vi.mock("@/components/Common/WaveformCanvas", () => ({
  __esModule: true,
  default: ({ label }: { label?: string }) => (
    <div data-testid="waveform" aria-label={label} />
  )
}))

// Mock HTMLAudioElement
const mockAudio = {
  play: vi.fn().mockResolvedValue(undefined),
  pause: vi.fn(),
  load: vi.fn(),
  removeAttribute: vi.fn(),
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  currentTime: 0,
  duration: 120,
  src: "",
  preload: ""
}

describe("UnifiedAudioPlayer", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders with idle state when no audioUrl", () => {
    render(<UnifiedAudioPlayer />)
    const playButton = screen.getByRole("button", { name: "Play" })
    expect(playButton).toBeDisabled()
  })

  it("renders play button when audioUrl is provided", () => {
    render(<UnifiedAudioPlayer audioUrl="blob:test" />)
    const playButton = screen.getByRole("button", { name: "Play" })
    expect(playButton).not.toBeDisabled()
  })

  it("renders region with correct aria-label", () => {
    render(<UnifiedAudioPlayer label="Test player" />)
    expect(screen.getByRole("region", { name: "Test player" })).toBeInTheDocument()
  })

  it("shows streaming indicator when isStreaming is true", () => {
    render(<UnifiedAudioPlayer isStreaming />)
    expect(screen.getByText("Streaming...")).toBeInTheDocument()
  })

  it("does not show streaming indicator by default", () => {
    render(<UnifiedAudioPlayer />)
    expect(screen.queryByText("Streaming...")).not.toBeInTheDocument()
  })

  it("renders time display", () => {
    render(<UnifiedAudioPlayer audioUrl="blob:test" />)
    expect(screen.getByText("0:00 / 0:00")).toBeInTheDocument()
  })

  it("shows download button when audioUrl is provided", () => {
    render(<UnifiedAudioPlayer audioUrl="blob:test" />)
    expect(screen.getByRole("button", { name: "Download audio" })).toBeInTheDocument()
  })

  it("does not show download button when no audio", () => {
    render(<UnifiedAudioPlayer />)
    expect(screen.queryByRole("button", { name: "Download audio" })).not.toBeInTheDocument()
  })
})
