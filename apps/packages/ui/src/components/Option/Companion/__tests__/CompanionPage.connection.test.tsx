import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { MemoryRouter } from "react-router-dom"

import { CompanionPage } from "../CompanionPage"

const mocks = vi.hoisted(() => ({
  isOnline: true,
  uxState: "connected_ok" as
    | "connected_ok"
    | "configuring_url"
    | "configuring_auth"
    | "error_auth"
    | "error_unreachable"
    | "unconfigured",
  hasCompletedFirstRun: true,
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
    hasCompletedFirstRun: mocks.hasCompletedFirstRun
  })
}))

vi.mock("@/hooks/useServerCapabilities", () => ({
  useServerCapabilities: () => ({
    capabilities: { hasPersona: true, hasPersonalization: true },
    loading: false
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

vi.mock("@/services/companion", () => ({
  createCompanionGoal: vi.fn(),
  fetchCompanionKnowledgeDetail: vi.fn(),
  fetchCompanionReflectionDetail: vi.fn(),
  fetchPersonalizationProfile: vi.fn(),
  fetchCompanionWorkspaceSnapshot: vi.fn(),
  purgeCompanionScope: vi.fn(),
  queueCompanionRebuild: vi.fn(),
  recordCompanionCheckIn: vi.fn(),
  setCompanionGoalStatus: vi.fn(),
  updateCompanionPreferences: vi.fn(),
  updatePersonalizationOptIn: vi.fn()
}))

describe("CompanionPage connection states", () => {
  beforeEach(() => {
    mocks.isOnline = true
    mocks.uxState = "connected_ok"
    mocks.hasCompletedFirstRun = true
    mocks.navigate.mockReset()
  })

  it("shows auth guidance instead of the generic offline state when credentials are missing", () => {
    mocks.isOnline = false
    mocks.uxState = "error_auth"

    render(
      <MemoryRouter>
        <CompanionPage surface="options" />
      </MemoryRouter>
    )

    expect(
      screen.getByText("Add your credentials to use Companion")
    ).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Settings" }))
    expect(mocks.navigate).toHaveBeenCalledWith("/settings/tldw")
  })

  it("keeps setup recovery inside the sidepanel shell", () => {
    mocks.isOnline = false
    mocks.uxState = "unconfigured"
    mocks.hasCompletedFirstRun = false

    render(
      <MemoryRouter>
        <CompanionPage surface="sidepanel" />
      </MemoryRouter>
    )

    expect(
      screen.getByText("Finish setup to use Companion")
    ).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Settings" }))
    expect(mocks.navigate).toHaveBeenCalledWith("/settings")
  })

  it("routes unreachable states to diagnostics in the options shell", () => {
    mocks.isOnline = false
    mocks.uxState = "error_unreachable"

    render(
      <MemoryRouter>
        <CompanionPage surface="options" />
      </MemoryRouter>
    )

    expect(
      screen.getByText("Can't reach your tldw server right now")
    ).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Health & diagnostics" }))
    expect(mocks.navigate).toHaveBeenCalledWith("/settings/health")
  })
})
