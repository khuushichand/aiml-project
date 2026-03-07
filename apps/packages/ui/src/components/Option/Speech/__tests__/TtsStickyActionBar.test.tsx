import React from "react"
import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"
import { TtsStickyActionBar } from "../TtsStickyActionBar"

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => fallback || key,
  }),
}))

function defaultProps(overrides: Partial<React.ComponentProps<typeof TtsStickyActionBar>> = {}) {
  return {
    onPlay: vi.fn(),
    onStop: vi.fn(),
    onDownloadSegment: vi.fn(),
    onDownloadAll: vi.fn(),
    onToggleInspector: vi.fn(),
    isPlayDisabled: false,
    isStopDisabled: false,
    isDownloadDisabled: false,
    playDisabledReason: null,
    stopDisabledReason: null,
    downloadDisabledReason: null,
    streamStatus: "idle" as const,
    inspectorOpen: false,
    inspectorBadge: "none" as const,
    segmentCount: 0,
    provider: "openai",
    ...overrides,
  }
}

describe("TtsStickyActionBar", () => {
  it("renders Play, Stop, Download buttons", () => {
    render(<TtsStickyActionBar {...defaultProps()} />)
    expect(screen.getByRole("button", { name: /play/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /stop/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /download/i })).toBeInTheDocument()
  })

  it("has role='toolbar'", () => {
    render(<TtsStickyActionBar {...defaultProps()} />)
    expect(screen.getByRole("toolbar")).toBeInTheDocument()
  })

  it("calls onPlay when Play clicked", () => {
    const onPlay = vi.fn()
    render(<TtsStickyActionBar {...defaultProps({ onPlay })} />)
    fireEvent.click(screen.getByRole("button", { name: /play/i }))
    expect(onPlay).toHaveBeenCalledTimes(1)
  })

  it("disables Play when isPlayDisabled is true", () => {
    render(<TtsStickyActionBar {...defaultProps({ isPlayDisabled: true })} />)
    expect(screen.getByRole("button", { name: /play/i })).toBeDisabled()
  })

  it("shows disabled reason text when Play is disabled with a reason", () => {
    render(
      <TtsStickyActionBar
        {...defaultProps({
          isPlayDisabled: true,
          playDisabledReason: "No text entered",
        })}
      />
    )
    expect(screen.getByText("No text entered")).toBeInTheDocument()
  })

  it("calls onToggleInspector when gear clicked", () => {
    const onToggleInspector = vi.fn()
    render(<TtsStickyActionBar {...defaultProps({ onToggleInspector })} />)
    const gearButton = screen.getByRole("button", { name: /configuration/i })
    fireEvent.click(gearButton)
    expect(onToggleInspector).toHaveBeenCalledTimes(1)
  })
})
