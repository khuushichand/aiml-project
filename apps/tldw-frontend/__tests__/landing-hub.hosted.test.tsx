import React from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"

import { ConnectionPhase } from "@/types/connection"
import OptionIndex from "@/routes/option-index"

const state = {
  hasCompletedFirstRun: false
}

let phase: ConnectionPhase | null = ConnectionPhase.UNCONFIGURED

const checkOnceMock = vi.fn().mockResolvedValue(undefined)
const beginOnboardingMock = vi.fn().mockResolvedValue(undefined)
const markFirstRunCompleteMock = vi.fn().mockResolvedValue(undefined)

vi.mock("~/components/Layouts/Layout", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="option-layout">{children}</div>
  )
}))

vi.mock("@/hooks/useConnectionState", () => ({
  useConnectionState: () => ({
    phase
  }),
  useConnectionUxState: () => ({
    uxState: null,
    hasCompletedFirstRun: state.hasCompletedFirstRun
  }),
  useConnectionActions: () => ({
    checkOnce: checkOnceMock,
    beginOnboarding: beginOnboardingMock,
    markFirstRunComplete: markFirstRunCompleteMock
  })
}))

vi.mock("@/hooks/useComposerFocus", () => ({
  useFocusComposerOnConnect: () => undefined
}))

vi.mock("@/hooks/useDarkmode", () => ({
  useDarkMode: () => ({
    mode: "dark",
    toggleDarkMode: vi.fn()
  })
}))

vi.mock("react-router-dom", () => ({
  Link: ({
    to,
    children,
    ...rest
  }: {
    to: string
    children: React.ReactNode
  }) => (
    <a href={to} {...rest}>
      {children}
    </a>
  )
}))

vi.mock("@/components/Option/Onboarding/OnboardingWizard", () => ({
  OnboardingWizard: () => <div data-testid="onboarding-wizard">Wizard</div>
}))

vi.mock("~/components/Option/LandingHub", () => ({
  LandingHub: () => <div data-testid="landing-hub">Landing hub</div>
}))

describe("OptionIndex hosted landing", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE = "hosted"
    state.hasCompletedFirstRun = false
    phase = ConnectionPhase.UNCONFIGURED
  })

  it("shows hosted landing content instead of the self-host onboarding wizard", () => {
    render(<OptionIndex />)

    expect(screen.getByRole("link", { name: /start trial/i })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /view self-host docs/i })).toBeInTheDocument()
    expect(screen.queryByTestId("onboarding-wizard")).toBeNull()
    expect(screen.queryByText(/home onboarding/i)).toBeNull()
    expect(checkOnceMock).not.toHaveBeenCalled()
    expect(beginOnboardingMock).not.toHaveBeenCalled()
  })
})
