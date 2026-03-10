import React from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import OptionIndex from "../option-index"
import OptionSetup from "../option-setup"
import OptionOnboardingTest from "../option-onboarding-test"

const state = {
  hasCompletedFirstRun: false
}
const toggleDarkModeMock = vi.fn()

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

vi.mock("@/hooks/useDarkmode", () => ({
  useDarkMode: () => ({
    mode: "dark",
    toggleDarkMode: toggleDarkModeMock
  })
}))

vi.mock("react-router-dom", () => ({
  useNavigate: () => navigateMock
}))

vi.mock("@/components/Option/Onboarding/OnboardingWizard", () => ({
  OnboardingWizard: ({
    onFinish
  }: {
    onFinish?: () => void | Promise<void>
  }) => (
    <div>
      <div data-testid="onboarding-wizard">Wizard</div>
      <button
        data-testid="onboarding-finish"
        onClick={() => {
          void onFinish?.()
        }}
      >
        Finish onboarding
      </button>
    </div>
  )
}))

vi.mock("~/components/Option/LandingHub", () => ({
  LandingHub: () => <div data-testid="landing-hub">Hub</div>
}))

describe("core route identity guardrails", () => {
  beforeEach(() => {
    optionLayoutMock.mockClear()
    navigateMock.mockClear()
    checkOnceMock.mockReset().mockResolvedValue(undefined)
    beginOnboardingMock.mockReset().mockResolvedValue(undefined)
    markFirstRunCompleteMock.mockReset().mockResolvedValue(undefined)
    toggleDarkModeMock.mockReset()
    state.hasCompletedFirstRun = false
  })

  it("provides unique route-intent headings for home/setup/onboarding-test", () => {
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

  it("completes onboarding immediately without waiting for connection recheck", async () => {
    optionLayoutMock.mockClear()
    state.hasCompletedFirstRun = false

    let resolveCheck: (() => void) | null = null
    checkOnceMock.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolveCheck = resolve
        })
    )

    render(<OptionIndex />)
    expect(screen.getByTestId("onboarding-wizard")).toBeInTheDocument()

    checkOnceMock.mockClear()
    markFirstRunCompleteMock.mockClear()

    fireEvent.click(screen.getByTestId("onboarding-finish"))

    await waitFor(() => {
      expect(markFirstRunCompleteMock).toHaveBeenCalledTimes(1)
    })
    expect(checkOnceMock).toHaveBeenCalledTimes(1)

    // Prevent unresolved Promise leakage in this test process.
    resolveCheck?.()
  })

  it("keeps an explicit theme toggle available on the home onboarding shell", () => {
    render(<OptionIndex />)

    const toggle = screen.getByTestId("chat-header-theme-toggle")
    expect(toggle).toBeInTheDocument()

    fireEvent.click(toggle)

    expect(toggleDarkModeMock).toHaveBeenCalledTimes(1)
  })
})
