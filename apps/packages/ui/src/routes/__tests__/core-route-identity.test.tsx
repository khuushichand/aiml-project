import React from "react"
import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import OptionIndex from "../option-index"
import OptionSetup from "../option-setup"
import OptionOnboardingTest from "../option-onboarding-test"

const state = {
  hasCompletedFirstRun: false
}

const optionLayoutMock = vi.fn(
  ({
    children
  }: {
    children: React.ReactNode
    hideHeader?: boolean
    hideSidebar?: boolean
  }) => <div data-testid="option-layout">{children}</div>
)

const checkOnceMock = vi.fn().mockResolvedValue(undefined)
const beginOnboardingMock = vi.fn().mockResolvedValue(undefined)
const markFirstRunCompleteMock = vi.fn().mockResolvedValue(undefined)
const navigateMock = vi.fn()

vi.mock("~/components/Layouts/Layout", () => ({
  __esModule: true,
  default: (props: {
    children: React.ReactNode
    hideHeader?: boolean
    hideSidebar?: boolean
  }) => optionLayoutMock(props)
}))

vi.mock("@/hooks/useConnectionState", () => ({
  useConnectionState: () => ({
    phase: null
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

vi.mock("react-router-dom", () => ({
  useNavigate: () => navigateMock
}))

vi.mock("@/components/Option/Onboarding/OnboardingWizard", () => ({
  OnboardingWizard: () => <div data-testid="onboarding-wizard">Wizard</div>
}))

vi.mock("~/components/Option/LandingHub", () => ({
  LandingHub: () => <div data-testid="landing-hub">Hub</div>
}))

describe("core route identity guardrails", () => {
  it("provides unique route-intent headings for home/setup/onboarding-test", () => {
    optionLayoutMock.mockClear()
    state.hasCompletedFirstRun = false

    const firstRender = render(<OptionIndex />)
    expect(screen.getByText("Home Onboarding")).toBeInTheDocument()
    expect(screen.getByTestId("onboarding-wizard")).toBeInTheDocument()
    expect(optionLayoutMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        hideHeader: true,
        hideSidebar: true
      })
    )
    firstRender.unmount()

    const secondRender = render(<OptionSetup />)
    expect(screen.getByText("Setup Wizard")).toBeInTheDocument()
    expect(screen.getByTestId("onboarding-wizard")).toBeInTheDocument()
    expect(optionLayoutMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        hideHeader: true,
        hideSidebar: true
      })
    )
    secondRender.unmount()

    render(<OptionOnboardingTest />)
    expect(screen.getByText("Onboarding Test Harness")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Go to setup" })).toBeInTheDocument()
    expect(screen.getByTestId("onboarding-wizard")).toBeInTheDocument()
    expect(optionLayoutMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        hideHeader: true,
        hideSidebar: true
      })
    )
  })
})
