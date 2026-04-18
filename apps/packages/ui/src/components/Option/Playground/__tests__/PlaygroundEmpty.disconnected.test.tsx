import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi, beforeEach } from "vitest"
import { PlaygroundEmpty } from "../PlaygroundEmpty"

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

vi.mock("@/hooks/useConnectionState", () => ({
  useIsConnected: () => false
}))

vi.mock("@/store/tutorials", () => ({
  useHelpModal: () => ({ open: vi.fn() })
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
    title: React.ReactNode
    description: React.ReactNode
    primaryActionLabel?: React.ReactNode
    onPrimaryAction?: () => void
    secondaryActionLabel?: string
    onSecondaryAction?: () => void
  }) => (
    <div>
      <h2>{title}</h2>
      <div data-testid="empty-state-description">{description}</div>
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

describe("PlaygroundEmpty – disconnected state", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders an Open Settings button when disconnected", () => {
    render(<PlaygroundEmpty />)

    const settingsButton = screen.getByRole("button", {
      name: /open settings/i
    })
    expect(settingsButton).toBeInTheDocument()
  })

  it("navigates to /settings/tldw when Open Settings is clicked", () => {
    render(<PlaygroundEmpty />)

    const settingsButton = screen.getByRole("button", {
      name: /open settings/i
    })
    fireEvent.click(settingsButton)

    expect(navigate).toHaveBeenCalledWith("/settings/tldw")
  })
})
