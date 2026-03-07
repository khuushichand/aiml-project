import { render, screen, fireEvent } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { TtsInspectorPanel } from "../TtsInspectorPanel"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => fallback || key
  })
}))

describe("TtsInspectorPanel", () => {
  const voiceTab = <div data-testid="voice-tab">Voice content</div>
  const outputTab = <div data-testid="output-tab">Output content</div>
  const advancedTab = <div data-testid="advanced-tab">Advanced content</div>

  it("renders with Voice tab active by default", () => {
    render(
      <TtsInspectorPanel
        open
        activeTab="voice"
        onTabChange={vi.fn()}
        onClose={vi.fn()}
        voiceTab={voiceTab}
        outputTab={outputTab}
        advancedTab={advancedTab}
      />
    )
    expect(screen.getByTestId("voice-tab")).toBeInTheDocument()
  })

  it("switches to Output tab on click", () => {
    const onTabChange = vi.fn()
    render(
      <TtsInspectorPanel
        open
        activeTab="voice"
        onTabChange={onTabChange}
        onClose={vi.fn()}
        voiceTab={voiceTab}
        outputTab={outputTab}
        advancedTab={advancedTab}
      />
    )
    fireEvent.click(screen.getByText("Output"))
    expect(onTabChange).toHaveBeenCalledWith("output")
  })

  it("calls onClose when close button is clicked", () => {
    const onClose = vi.fn()
    render(
      <TtsInspectorPanel
        open
        activeTab="voice"
        onTabChange={vi.fn()}
        onClose={onClose}
        voiceTab={voiceTab}
        outputTab={outputTab}
        advancedTab={advancedTab}
      />
    )
    fireEvent.click(screen.getByRole("button", { name: /close/i }))
    expect(onClose).toHaveBeenCalledOnce()
  })

  it("does not render content when closed", () => {
    render(
      <TtsInspectorPanel
        open={false}
        activeTab="voice"
        onTabChange={vi.fn()}
        onClose={vi.fn()}
        voiceTab={voiceTab}
        outputTab={outputTab}
        advancedTab={advancedTab}
      />
    )
    expect(screen.queryByTestId("voice-tab")).not.toBeInTheDocument()
  })
})
