import React from "react"
import { render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  isOnline: true,
  capabilitiesState: {
    capabilities: { hasPersonalization: true },
    loading: false
  } as {
    capabilities: { hasPersonalization: boolean } | null
    loading: boolean
  },
  fetchCompanionWorkspaceSnapshot: vi.fn(),
  recordExplicitCompanionCapture: vi.fn()
}))

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => mocks.isOnline
}))

vi.mock("@/hooks/useServerCapabilities", () => ({
  useServerCapabilities: () => mocks.capabilitiesState
}))

vi.mock("@/components/Common/RouteErrorBoundary", () => ({
  RouteErrorBoundary: ({ children }: { children: React.ReactNode }) => <>{children}</>
}))

vi.mock("@/services/companion", () => ({
  fetchCompanionWorkspaceSnapshot: (...args: unknown[]) =>
    mocks.fetchCompanionWorkspaceSnapshot(...args),
  recordExplicitCompanionCapture: (...args: unknown[]) =>
    mocks.recordExplicitCompanionCapture(...args)
}))

vi.mock("~/components/Sidepanel/Chat/SidepanelHeaderSimple", () => ({
  SidepanelHeaderSimple: ({ activeTitle }: { activeTitle?: string }) => (
    <div data-testid="sidepanel-header">{activeTitle || "header"}</div>
  )
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      defaultValueOrOptions?:
        | string
        | {
            defaultValue?: string
          }
    ) => {
      if (typeof defaultValueOrOptions === "string") return defaultValueOrOptions
      if (defaultValueOrOptions?.defaultValue) return defaultValueOrOptions.defaultValue
      return key
    }
  })
}))

import SidepanelCompanion from "../sidepanel-companion"

describe("SidepanelCompanion", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.sessionStorage.clear()
    mocks.isOnline = true
    mocks.capabilitiesState.capabilities = { hasPersonalization: true }
    mocks.capabilitiesState.loading = false
    mocks.fetchCompanionWorkspaceSnapshot.mockResolvedValue({
      activity: [],
      activityTotal: 0,
      knowledge: [],
      knowledgeTotal: 0,
      goals: [],
      activeGoalCount: 0,
      reflections: [],
      reflectionNotifications: []
    })
    mocks.recordExplicitCompanionCapture.mockResolvedValue({
      id: "activity-1",
      event_type: "extension.selection_saved",
      source_type: "browser_selection",
      source_id: "capture-1",
      surface: "extension.sidepanel",
      tags: ["extension", "selection"],
      provenance: {
        capture_mode: "explicit",
        route: "extension.context_menu",
        action: "save_selection"
      },
      metadata: {
        selection: "Remember this paragraph.",
        page_url: "https://example.com/article",
        page_title: "Example article"
      },
      created_at: "2026-03-10T12:00:00Z"
    })
  })

  it("shows unavailable state when personalization capability is missing", () => {
    mocks.capabilitiesState.capabilities = { hasPersonalization: false }
    render(<SidepanelCompanion />)

    expect(screen.getByText("Companion unavailable")).toBeInTheDocument()
  })

  it("records the pending selection capture when the companion route opens", async () => {
    window.sessionStorage.setItem(
      "tldw:companion:pendingCapture",
      JSON.stringify({
        id: "capture-1",
        selectionText: "Remember this paragraph.",
        pageUrl: "https://example.com/article",
        pageTitle: "Example article",
        action: "save_selection"
      })
    )

    render(<SidepanelCompanion />)

    await waitFor(() => {
      expect(mocks.recordExplicitCompanionCapture).toHaveBeenCalledWith(
        expect.objectContaining({
          event_type: "extension.selection_saved",
          source_type: "browser_selection",
          source_id: "capture-1",
          surface: "extension.sidepanel",
          dedupe_key: "extension.selection_saved:capture-1",
          metadata: expect.objectContaining({
            selection: "Remember this paragraph.",
            page_url: "https://example.com/article",
            page_title: "Example article"
          }),
          provenance: expect.objectContaining({
            capture_mode: "explicit",
            action: "save_selection"
          })
        })
      )
    })
  })
})
