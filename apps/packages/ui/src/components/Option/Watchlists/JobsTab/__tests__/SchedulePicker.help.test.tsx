import React from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { SchedulePicker } from "../SchedulePicker"

const telemetryMock = vi.hoisted(() => ({
  trackWatchlistsPreventionTelemetry: vi.fn()
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, defaultValue?: unknown) =>
      typeof defaultValue === "string" ? defaultValue : _key
  })
}))

vi.mock("@/utils/watchlists-prevention-telemetry", () => ({
  trackWatchlistsPreventionTelemetry: (...args: any[]) =>
    telemetryMock.trackWatchlistsPreventionTelemetry(...args)
}))

describe("SchedulePicker contextual help", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    telemetryMock.trackWatchlistsPreventionTelemetry.mockResolvedValue(undefined)
    if (!window.matchMedia) {
      Object.defineProperty(window, "matchMedia", {
        writable: true,
        value: vi.fn().mockImplementation((query: string) => ({
          matches: false,
          media: query,
          onchange: null,
          addListener: vi.fn(),
          removeListener: vi.fn(),
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
          dispatchEvent: vi.fn()
        }))
      })
    }
  })

  it("shows a cron help trigger in the advanced schedule section", () => {
    render(<SchedulePicker value={null} onChange={vi.fn()} />)

    expect(screen.getByTestId("watchlists-help-cron")).toBeInTheDocument()
  })

  it("shows localized frequency guidance and emits prevention telemetry for too-frequent cron", async () => {
    const onChange = vi.fn()
    render(<SchedulePicker value={null} onChange={onChange} />)

    fireEvent.click(screen.getByRole("switch"))
    fireEvent.change(
      screen.getByPlaceholderText(
        "Advanced schedule expression (cron, e.g., 0 9 * * MON)"
      ),
      { target: { value: "* * * * *" } }
    )
    fireEvent.click(screen.getByRole("button", { name: "Apply" }))

    await waitFor(() => {
      expect(screen.getByText(/Schedule is too frequent/i)).toBeInTheDocument()
    })
    expect(onChange).not.toHaveBeenCalled()
    expect(telemetryMock.trackWatchlistsPreventionTelemetry).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "watchlists_validation_blocked",
        surface: "schedule_picker",
        rule: "schedule_too_frequent"
      })
    )
  })
})
