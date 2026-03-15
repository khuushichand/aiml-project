import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { MemoryRouter } from "react-router-dom"

import ConnectFeatureBanner from "../ConnectFeatureBanner"

const mocks = vi.hoisted(() => ({
  isOnline: true,
  uxState: "connected_ok" as
    | "connected_ok"
    | "testing"
    | "configuring_url"
    | "configuring_auth"
    | "error_auth"
    | "error_unreachable"
    | "unconfigured",
  navigate: vi.fn()
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback ?? _key
  })
}))

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>(
    "react-router-dom"
  )
  return {
    ...actual,
    useNavigate: () => mocks.navigate
  }
})

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => mocks.isOnline
}))

vi.mock("@/hooks/useConnectionState", () => ({
  useConnectionUxState: () => ({
    uxState: mocks.uxState,
    hasCompletedFirstRun: true
  })
}))

vi.mock("@/components/Common/FeatureEmptyState", () => ({
  default: ({
    title,
    description,
    examples,
    primaryActionLabel,
    onPrimaryAction,
    secondaryActionLabel,
    onSecondaryAction
  }: {
    title: React.ReactNode
    description?: React.ReactNode
    examples?: React.ReactNode[]
    primaryActionLabel?: React.ReactNode
    onPrimaryAction?: () => void
    secondaryActionLabel?: React.ReactNode
    onSecondaryAction?: () => void
  }) => (
    <div data-testid="feature-empty-state">
      <div>{title}</div>
      {description ? <div>{description}</div> : null}
      {examples?.map((example, index) => <div key={index}>{example}</div>)}
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

const renderBanner = () =>
  render(
    <MemoryRouter>
      <ConnectFeatureBanner
        title="Fallback title"
        description="Fallback description"
        examples={["Fallback example"]}
      />
    </MemoryRouter>
  )

describe("ConnectFeatureBanner connection states", () => {
  beforeEach(() => {
    mocks.isOnline = true
    mocks.uxState = "connected_ok"
    mocks.navigate.mockReset()
  })

  it("shows credential guidance when auth is missing", () => {
    mocks.isOnline = false
    mocks.uxState = "error_auth"

    renderBanner()

    expect(screen.getByText("Add your credentials to continue")).toBeInTheDocument()
    expect(screen.queryByText("Fallback title")).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Open Settings" }))
    expect(mocks.navigate).toHaveBeenCalledWith("/settings/tldw")
  })

  it("shows setup guidance and routes users to setup", () => {
    mocks.isOnline = false
    mocks.uxState = "unconfigured"

    renderBanner()

    expect(screen.getByText("Finish setup to continue")).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Finish Setup" }))
    expect(mocks.navigate).toHaveBeenCalledWith("/")
  })

  it("shows diagnostics guidance when the server is unreachable", () => {
    mocks.isOnline = false
    mocks.uxState = "error_unreachable"

    renderBanner()

    expect(
      screen.getByText("Can't reach your tldw server right now")
    ).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Health & diagnostics" }))
    fireEvent.click(screen.getByRole("button", { name: "Open Settings" }))

    expect(mocks.navigate).toHaveBeenCalledWith("/settings/health")
    expect(mocks.navigate).toHaveBeenCalledWith("/settings/tldw")
  })

  it("renders nothing while connection checks are still testing", () => {
    mocks.isOnline = false
    mocks.uxState = "testing"

    renderBanner()

    expect(screen.queryByTestId("feature-empty-state")).not.toBeInTheDocument()
  })
})
