import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi, beforeEach } from "vitest"
import { PlaygroundEmpty } from "../PlaygroundEmpty"

const openHelpModal = vi.fn()
const navigate = vi.fn()

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, arg?: string | { defaultValue?: string }) => {
      if (typeof arg === "string") return arg
      if (arg && typeof arg === "object" && arg.defaultValue) {
        return arg.defaultValue
      }
      return _key
    }
  })
}))

vi.mock("@/context/demo-mode", () => ({
  useDemoMode: () => ({ demoEnabled: false })
}))

vi.mock("@/store/tutorials", () => ({
  useHelpModal: () => ({ open: openHelpModal })
}))

vi.mock("react-router-dom", () => ({
  useNavigate: () => navigate
}))

vi.mock("@/components/Common/FeatureEmptyState", () => ({
  __esModule: true,
  default: ({
    title,
    description,
    primaryActionLabel,
    onPrimaryAction,
    secondaryActionLabel,
    onSecondaryAction
  }: {
    title: string
    description: string
    primaryActionLabel: string
    onPrimaryAction?: () => void
    secondaryActionLabel?: string
    onSecondaryAction?: () => void
  }) => (
    <div>
      <h2>{title}</h2>
      <p>{description}</p>
      {onPrimaryAction ? (
        <button type="button" onClick={onPrimaryAction}>
          {primaryActionLabel}
        </button>
      ) : null}
      {onSecondaryAction ? (
        <button type="button" onClick={onSecondaryAction}>
          {secondaryActionLabel}
        </button>
      ) : null}
    </div>
  )
}))

describe("PlaygroundEmpty", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("dispatches starter telemetry and starter action events when compare is selected", () => {
    const dispatchSpy = vi.spyOn(window, "dispatchEvent")
    render(<PlaygroundEmpty />)

    fireEvent.click(screen.getByRole("button", { name: /Compare models/i }))

    expect(dispatchSpy).toHaveBeenCalled()
    const compareEvent = dispatchSpy.mock.calls
      .map((call) => call[0])
      .find((event) => event.type === "tldw:playground-starter") as
      | CustomEvent
      | undefined
    expect(compareEvent).toBeDefined()
    expect((compareEvent as CustomEvent).detail).toMatchObject({
      mode: "compare"
    })

    const telemetryEvent = dispatchSpy.mock.calls
      .map((call) => call[0])
      .find(
        (event) => event.type === "tldw:playground-starter-selected"
      ) as CustomEvent | undefined
    expect(telemetryEvent).toBeDefined()
    expect((telemetryEvent as CustomEvent).detail).toMatchObject({
      mode: "compare"
    })
  })

  it("opens history and knowledge panel region actions", () => {
    const dispatchSpy = vi.spyOn(window, "dispatchEvent")
    render(<PlaygroundEmpty />)

    fireEvent.click(screen.getByRole("button", { name: "Open history" }))
    fireEvent.click(
      screen.getByRole("button", { name: "Open Search & Context" })
    )

    const eventTypes = dispatchSpy.mock.calls.map((call) => call[0].type)
    expect(eventTypes).toContain("tldw:open-chat-sidebar")
    expect(eventTypes).toContain("tldw:open-knowledge-panel")
  })

  it("opens the help modal from the quick tour action", () => {
    render(<PlaygroundEmpty />)

    fireEvent.click(screen.getByRole("button", { name: "Take a quick tour" }))

    expect(openHelpModal).toHaveBeenCalledTimes(1)
  })

  it("does not render the stale try-asking prompt suggestions", () => {
    render(<PlaygroundEmpty />)

    expect(screen.queryByText("Try asking:")).not.toBeInTheDocument()
    expect(
      screen.queryByText("Summarize the key points from my last uploaded document")
    ).not.toBeInTheDocument()
  })

  it("routes the deep research starter to the research console", () => {
    render(<PlaygroundEmpty />)

    fireEvent.click(screen.getByRole("button", { name: /Deep Research/i }))

    expect(navigate).toHaveBeenCalledWith("/research")
  })
})
