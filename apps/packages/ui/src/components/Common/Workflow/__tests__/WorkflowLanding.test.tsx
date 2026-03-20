import React from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom"

const mocks = vi.hoisted(() => ({
  startWorkflow: vi.fn(),
  setShowLanding: vi.fn(),
  dismissLanding: vi.fn(),
  loadLandingConfig: vi.fn()
}))

const workflowStoreState = {
  showLanding: true,
  landingConfig: {
    completedWorkflows: [] as string[]
  },
  setShowLanding: mocks.setShowLanding,
  dismissLanding: mocks.dismissLanding,
  startWorkflow: mocks.startWorkflow,
  loadLandingConfig: mocks.loadLandingConfig
}

vi.mock("@/store/workflows", () => ({
  useWorkflowsStore: (selector: (state: typeof workflowStoreState) => unknown) =>
    selector(workflowStoreState)
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, fallbackOrOptions?: string | { defaultValue?: string }) => {
      if (typeof fallbackOrOptions === "string") return fallbackOrOptions
      if (fallbackOrOptions?.defaultValue) return fallbackOrOptions.defaultValue
      return _key
    }
  })
}))

import { WorkflowLanding } from ".."

const LocationDisplay = () => {
  const location = useLocation()
  return <div data-testid="location">{location.pathname}</div>
}

const renderWorkflowLanding = (props?: Partial<React.ComponentProps<typeof WorkflowLanding>>) =>
  render(
    <MemoryRouter initialEntries={["/"]}>
      <LocationDisplay />
      <Routes>
        <Route path="/" element={<WorkflowLanding {...props} />} />
        <Route path="/research" element={<div>Research</div>} />
        <Route path="/media-multi" element={<div>Media Multi</div>} />
      </Routes>
    </MemoryRouter>
  )

beforeEach(() => {
  workflowStoreState.showLanding = true
  workflowStoreState.landingConfig.completedWorkflows = []
  mocks.startWorkflow.mockReset()
  mocks.setShowLanding.mockReset()
  mocks.dismissLanding.mockReset()
  mocks.loadLandingConfig.mockReset()
})

describe("WorkflowLanding", () => {
  it("navigates to research when clicking Do Research", async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    renderWorkflowLanding({ onClose })

    await user.click(screen.getByRole("button", { name: /do research/i }))

    await waitFor(() => {
      expect(screen.getByTestId("location")).toHaveTextContent("/research")
    })
    expect(mocks.setShowLanding).toHaveBeenCalledWith(false)
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it("navigates to media multi when clicking Perform Analysis", async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    renderWorkflowLanding({ onClose })

    await user.click(screen.getByRole("button", { name: /perform analysis/i }))

    await waitFor(() => {
      expect(screen.getByTestId("location")).toHaveTextContent("/media-multi")
    })
    expect(mocks.setShowLanding).toHaveBeenCalledWith(false)
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it("calls onJustChat when clicking Start Chatting", async () => {
    const user = userEvent.setup()
    const onJustChat = vi.fn()
    renderWorkflowLanding({ onJustChat })

    await user.click(screen.getByRole("button", { name: /start chatting/i }))

    expect(mocks.setShowLanding).toHaveBeenCalledWith(false)
    expect(onJustChat).toHaveBeenCalledTimes(1)
  })

  it("switches from the hub to the workflow catalog", async () => {
    const user = userEvent.setup()
    renderWorkflowLanding()

    await user.click(
      screen.getByRole("button", { name: /get started with a workflow/i })
    )

    expect(
      screen.getByRole("button", { name: /just chat/i })
    ).toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: /perform analysis/i })
    ).toBeNull()
  })
})
