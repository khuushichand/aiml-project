import React from "react"
import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import OptionTts from "../option-tts"
import OptionStt from "../option-stt"
import OptionSpeech from "../option-speech"

vi.mock("~/components/Layouts/Layout", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="option-layout">{children}</div>
  )
}))

vi.mock("@/components/Common/RouteErrorBoundary", () => ({
  RouteErrorBoundary: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  )
}))

vi.mock("@/components/Option/TTS/TtsPlaygroundPage", () => ({
  __esModule: true,
  default: () => <div data-testid="tts-playground">TTS</div>
}))

vi.mock("@/components/Option/STT/SttPlaygroundPage", () => ({
  __esModule: true,
  default: () => <div data-testid="stt-playground">STT</div>
}))

vi.mock("@/components/Option/Speech/SpeechPlaygroundPage", () => ({
  __esModule: true,
  default: ({ initialMode }: { initialMode?: string }) => (
    <div data-testid="speech-playground" data-mode={initialMode ?? "roundtrip"}>
      Speech
    </div>
  )
}))

describe("audio option routes", () => {
  it("renders dedicated TTS playground on /tts route component", () => {
    render(<OptionTts />)
    expect(screen.getByTestId("option-layout")).toBeVisible()
    expect(screen.getByTestId("tts-playground")).toBeVisible()
    expect(screen.queryByTestId("speech-playground")).not.toBeInTheDocument()
  })

  it("renders dedicated STT playground on /stt route component", () => {
    render(<OptionStt />)
    expect(screen.getByTestId("option-layout")).toBeVisible()
    expect(screen.getByTestId("stt-playground")).toBeVisible()
    expect(screen.queryByTestId("speech-playground")).not.toBeInTheDocument()
  })

  it("keeps /speech route mapped to the unified speech playground", () => {
    render(<OptionSpeech />)
    const speech = screen.getByTestId("speech-playground")
    expect(speech).toBeVisible()
    expect(speech).toHaveAttribute("data-mode", "roundtrip")
    expect(screen.queryByTestId("tts-playground")).not.toBeInTheDocument()
    expect(screen.queryByTestId("stt-playground")).not.toBeInTheDocument()
  })
})
