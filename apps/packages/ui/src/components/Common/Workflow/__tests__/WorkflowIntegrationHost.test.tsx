import React from "react"
import { render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { MemoryRouter } from "react-router-dom"

let hasCompletedFirstRun = true
let showLanding = false

const loadLandingConfigMock = vi.fn().mockResolvedValue(undefined)
const loadDismissedSuggestionsMock = vi.fn().mockResolvedValue(undefined)
const markLandingSeenMock = vi.fn()
const setShowLandingMock = vi.fn()

vi.mock("@/hooks/useConnectionState", () => ({
  useConnectionUxState: () => ({
    hasCompletedFirstRun
  })
}))

vi.mock("@/store/workflows", () => ({
  useWorkflowsStore: (
    selector: (state: {
      loadLandingConfig: typeof loadLandingConfigMock
      loadDismissedSuggestions: typeof loadDismissedSuggestionsMock
      markLandingSeen: typeof markLandingSeenMock
      showLanding: boolean
      setShowLanding: typeof setShowLandingMock
    }) => unknown
  ) =>
    selector({
      loadLandingConfig: loadLandingConfigMock,
      loadDismissedSuggestions: loadDismissedSuggestionsMock,
      markLandingSeen: markLandingSeenMock,
      showLanding,
      setShowLanding: setShowLandingMock
    })
}))

vi.mock("../WorkflowLanding", () => ({
  WorkflowLandingModal: () =>
    showLanding ? <div data-testid="workflow-landing-modal">Workflow landing</div> : null
}))

vi.mock("../WorkflowContainer", () => ({
  WorkflowOverlay: () => <div data-testid="workflow-overlay" />
}))

import { WorkflowIntegrationHost } from "../WorkflowIntegrationHost"

const renderHost = (path: string, autoShowPaths: string[]) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <WorkflowIntegrationHost autoShowPaths={autoShowPaths} />
    </MemoryRouter>
  )

describe("WorkflowIntegrationHost", () => {
  beforeEach(() => {
    hasCompletedFirstRun = true
    showLanding = false
    loadLandingConfigMock.mockClear()
    loadDismissedSuggestionsMock.mockClear()
    markLandingSeenMock.mockClear()
    setShowLandingMock.mockClear()
  })

  it("does not auto-open workflow landing on the dedicated home route", async () => {
    renderHost("/", ["/"])

    await waitFor(() => {
      expect(loadDismissedSuggestionsMock).toHaveBeenCalledTimes(1)
    })

    expect(loadLandingConfigMock).not.toHaveBeenCalled()
    expect(screen.queryByTestId("workflow-landing-modal")).toBeNull()
  })

  it("still auto-loads workflow landing on non-home routes when configured", async () => {
    renderHost("/knowledge", ["/knowledge"])

    await waitFor(() => {
      expect(loadLandingConfigMock).toHaveBeenCalledTimes(1)
    })

    expect(loadDismissedSuggestionsMock).toHaveBeenCalledTimes(1)
  })
})
