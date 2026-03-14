import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import OptionMediaMulti from "../option-media-multi"

const mocks = vi.hoisted(() => ({
  isOnline: true,
  demoEnabled: false,
  uxState: "connected_ok" as
    | "connected_ok"
    | "testing"
    | "configuring_url"
    | "configuring_auth"
    | "error_auth"
    | "error_unreachable"
    | "unconfigured",
  hasCompletedFirstRun: true,
  navigate: vi.fn()
}))

vi.mock("~/components/Layouts/Layout", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <div>{children}</div>
}))

vi.mock("@/components/Common/RouteErrorBoundary", () => ({
  RouteErrorBoundary: ({ children }: { children: React.ReactNode }) => <div>{children}</div>
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      _key: string,
      defaultValueOrOptions?:
        | string
        | {
            defaultValue?: string
          }
    ) => {
      if (typeof defaultValueOrOptions === "string") return defaultValueOrOptions
      return defaultValueOrOptions?.defaultValue ?? _key
    }
  })
}))

vi.mock("react-router-dom", () => ({
  useNavigate: () => mocks.navigate
}))

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => mocks.isOnline
}))

vi.mock("@/hooks/useConnectionState", () => ({
  useConnectionUxState: () => ({
    uxState: mocks.uxState,
    hasCompletedFirstRun: mocks.hasCompletedFirstRun
  })
}))

vi.mock("@/hooks/useServerCapabilities", () => ({
  useServerCapabilities: () => ({
    loading: false,
    capabilities: {
      hasMedia: true
    }
  })
}))

vi.mock("@/context/demo-mode", () => ({
  useDemoMode: () => ({
    demoEnabled: mocks.demoEnabled
  })
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
    title?: React.ReactNode
    description?: React.ReactNode
    primaryActionLabel?: React.ReactNode
    onPrimaryAction?: () => void
    secondaryActionLabel?: React.ReactNode
    onSecondaryAction?: () => void
  }) => (
    <div data-testid="feature-empty-state">
      <h2>{title}</h2>
      {description ? <p>{description}</p> : null}
      {primaryActionLabel ? (
        <button type="button" onClick={onPrimaryAction}>
          {primaryActionLabel}
        </button>
      ) : null}
      {secondaryActionLabel ? (
        <button type="button" onClick={onSecondaryAction}>
          {secondaryActionLabel}
        </button>
      ) : null}
    </div>
  )
}))

vi.mock("@/components/Review/MediaReviewPage", () => ({
  __esModule: true,
  default: () => <div data-testid="media-review-page">Media review</div>
}))

describe("OptionMediaMulti connection states", () => {
  beforeEach(() => {
    mocks.isOnline = true
    mocks.demoEnabled = false
    mocks.uxState = "connected_ok"
    mocks.hasCompletedFirstRun = true
    mocks.navigate.mockReset()
  })

  it("keeps demo preview visible while surfacing auth guidance", () => {
    mocks.isOnline = false
    mocks.demoEnabled = true
    mocks.uxState = "error_auth"

    render(<OptionMediaMulti />)

    expect(screen.getByText("Explore Media in demo mode")).toBeInTheDocument()
    expect(screen.getByText("Example media items (preview only)")).toBeInTheDocument()
    expect(
      screen.getByText("Demo stays available, but your Media credentials need attention.")
    ).toBeInTheDocument()
  })

  it("shows setup guidance when demo mode is disabled", () => {
    mocks.isOnline = false
    mocks.demoEnabled = false
    mocks.uxState = "unconfigured"
    mocks.hasCompletedFirstRun = false

    render(<OptionMediaMulti />)

    expect(screen.getByText("Finish setup to use Media")).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Finish Setup" }))
    expect(mocks.navigate).toHaveBeenCalledWith("/")
  })

  it("shows unreachable guidance with diagnostics navigation", () => {
    mocks.isOnline = false
    mocks.demoEnabled = false
    mocks.uxState = "error_unreachable"

    render(<OptionMediaMulti />)

    expect(
      screen.getByText("Can't reach your tldw server right now")
    ).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Health & diagnostics" }))
    expect(mocks.navigate).toHaveBeenCalledWith("/settings/health")
  })
})
