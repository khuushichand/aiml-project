// @vitest-environment jsdom

import React from "react"
import { existsSync, readFileSync } from "node:fs"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"

const mocks = vi.hoisted(() => ({
  isOnline: true,
  capabilitiesState: {
    capabilities: {
      hasPersonalization: true,
      hasPersona: true
    },
    loading: false
  } as {
    capabilities:
      | {
          hasPersonalization: boolean
          hasPersona: boolean
        }
      | null
    loading: boolean
  },
  fetchSnapshot: vi.fn(),
  setGoalStatus: vi.fn(),
  createGoal: vi.fn(),
  recordCheckIn: vi.fn()
}))

vi.mock("@/components/Layouts/Layout", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="option-layout">{children}</div>
  )
}))

vi.mock("@/components/Common/RouteErrorBoundary", () => ({
  RouteErrorBoundary: ({ children }: { children: React.ReactNode }) => <>{children}</>
}))

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => mocks.isOnline
}))

vi.mock("@/hooks/useServerCapabilities", () => ({
  useServerCapabilities: () => mocks.capabilitiesState
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

vi.mock("@/services/companion", () => ({
  fetchCompanionWorkspaceSnapshot: (...args: unknown[]) =>
    mocks.fetchSnapshot(...args),
  setCompanionGoalStatus: (...args: unknown[]) => mocks.setGoalStatus(...args),
  createCompanionGoal: (...args: unknown[]) => mocks.createGoal(...args),
  recordCompanionCheckIn: (...args: unknown[]) => mocks.recordCheckIn(...args)
}))

import OptionCompanion from "../option-companion"

const routeRegistryPathCandidates = [
  "src/routes/route-registry.tsx",
  "../packages/ui/src/routes/route-registry.tsx",
  "apps/packages/ui/src/routes/route-registry.tsx"
]

const routeRegistryPath = routeRegistryPathCandidates.find((candidate) =>
  existsSync(candidate)
)

if (!routeRegistryPath) {
  throw new Error("Unable to locate route-registry.tsx for companion route test")
}

const routeRegistrySource = readFileSync(routeRegistryPath, "utf8")

const activeSnapshot = {
  activity: [
    {
      id: "activity-1",
      event_type: "reading.saved",
      source_type: "reading_item",
      source_id: "42",
      surface: "reading",
      tags: ["research"],
      provenance: { capture_mode: "explicit" },
      metadata: { title: "Example article" },
      created_at: "2026-03-10T12:00:00Z"
    }
  ],
  activityTotal: 1,
  knowledge: [
    {
      id: "knowledge-1",
      card_type: "project_focus",
      title: "Project alpha",
      summary: "Recent activity clusters around project alpha.",
      evidence: [{ source_id: "42" }],
      score: 0.9,
      status: "active",
      updated_at: "2026-03-10T12:30:00Z"
    }
  ],
  goals: [
    {
      id: "goal-1",
      title: "Finish queue",
      description: "Read three saved papers.",
      goal_type: "reading_backlog",
      config: { target_count: 3 },
      progress: { completed_count: 1 },
      status: "active",
      created_at: "2026-03-10T09:00:00Z",
      updated_at: "2026-03-10T10:00:00Z"
    }
  ],
  activeGoalCount: 1,
  knowledgeTotal: 1,
  reflections: [
    {
      id: "reflection-1",
      cadence: "daily",
      summary: "You revisited project alpha.",
      evidence: [{ source_id: "42" }],
      created_at: "2026-03-10T13:00:00Z"
    }
  ],
  reflectionNotifications: [
    {
      id: 11,
      user_id: "1",
      kind: "companion_reflection",
      title: "Daily reflection",
      message: "You revisited project alpha.",
      severity: "info",
      link_type: "companion_reflection",
      link_id: "reflection-1",
      created_at: "2026-03-10T13:00:00Z",
      read_at: null,
      dismissed_at: null
    }
  ]
}

const pausedSnapshot = {
  ...activeSnapshot,
  goals: [
    {
      ...activeSnapshot.goals[0],
      status: "paused",
      updated_at: "2026-03-10T10:05:00Z"
    }
  ],
  activeGoalCount: 0
}

const renderRoute = () =>
  render(
    <MemoryRouter>
      <OptionCompanion />
    </MemoryRouter>
  )

describe("option companion route", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.isOnline = true
    mocks.capabilitiesState.capabilities = {
      hasPersonalization: true,
      hasPersona: true
    }
    mocks.capabilitiesState.loading = false
    mocks.fetchSnapshot.mockResolvedValue(activeSnapshot)
    mocks.setGoalStatus.mockResolvedValue({
      ...activeSnapshot.goals[0],
      status: "paused"
    })
    mocks.createGoal.mockResolvedValue({
      id: "goal-2",
      title: "Capture a weekly review",
      description: null,
      goal_type: "manual",
      config: {},
      progress: {},
      status: "active",
      created_at: "2026-03-10T14:00:00Z",
      updated_at: "2026-03-10T14:00:00Z"
    })
    mocks.recordCheckIn.mockResolvedValue({
      id: "activity-checkin-1",
      event_type: "companion_check_in_recorded",
      source_type: "companion_check_in",
      source_id: "checkin-1",
      surface: "companion.workspace",
      tags: ["planning", "focus"],
      provenance: {
        capture_mode: "explicit",
        route: "/api/v1/companion/check-ins",
        action: "manual_check_in"
      },
      metadata: {
        title: "Morning reset",
        summary: "Re-focused on the companion capture backlog before lunch."
      },
      created_at: "2026-03-10T14:30:00Z"
    })
  })

  it("renders the companion workspace inside the option layout", async () => {
    renderRoute()

    expect(screen.getByTestId("option-layout")).toBeInTheDocument()
    expect(await screen.findByTestId("companion-page")).toBeInTheDocument()
    expect(screen.getByText("Example article")).toBeInTheDocument()
    expect(screen.getByText("Project alpha")).toBeInTheDocument()
    expect(screen.getByText("Finish queue")).toBeInTheDocument()
    expect(screen.getByText("You revisited project alpha.")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Open collections" })).toHaveAttribute(
      "href",
      "/collections"
    )
  })

  it("allows pausing a goal and refreshes the workspace snapshot", async () => {
    mocks.fetchSnapshot.mockResolvedValueOnce(activeSnapshot).mockResolvedValueOnce(
      pausedSnapshot
    )

    renderRoute()

    await screen.findByText("Finish queue")
    fireEvent.click(screen.getByRole("button", { name: "Pause" }))

    await waitFor(() => {
      expect(mocks.setGoalStatus).toHaveBeenCalledWith("goal-1", "paused")
    })
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Resume" })).toBeInTheDocument()
    })
  })

  it("records a manual check-in and refreshes the activity list", async () => {
    const checkInSnapshot = {
      ...activeSnapshot,
      activity: [
        {
          id: "activity-checkin-1",
          event_type: "companion_check_in_recorded",
          source_type: "companion_check_in",
          source_id: "checkin-1",
          surface: "companion.workspace",
          tags: ["planning", "focus"],
          provenance: {
            capture_mode: "explicit",
            route: "/api/v1/companion/check-ins",
            action: "manual_check_in"
          },
          metadata: {
            title: "Morning reset",
            summary: "Re-focused on the companion capture backlog before lunch."
          },
          created_at: "2026-03-10T14:30:00Z"
        },
        ...activeSnapshot.activity
      ],
      activityTotal: 2
    }
    mocks.fetchSnapshot.mockResolvedValueOnce(activeSnapshot).mockResolvedValueOnce(
      checkInSnapshot
    )

    renderRoute()

    await screen.findByText("Example article")
    fireEvent.change(screen.getByLabelText("Check-in title"), {
      target: { value: "Morning reset" }
    })
    fireEvent.change(screen.getByLabelText("Summary"), {
      target: {
        value: "Re-focused on the companion capture backlog before lunch."
      }
    })
    fireEvent.change(screen.getByLabelText("Tags"), {
      target: { value: "planning, focus" }
    })
    fireEvent.click(screen.getByRole("button", { name: "Save check-in" }))

    await waitFor(() => {
      expect(mocks.recordCheckIn).toHaveBeenCalledWith({
        title: "Morning reset",
        summary: "Re-focused on the companion capture backlog before lunch.",
        tags: ["planning", "focus"]
      })
    })
    await waitFor(() => {
      expect(screen.getByText("Morning reset")).toBeInTheDocument()
    })
  })

  it("shows an unavailable state when personalization support is missing", async () => {
    mocks.capabilitiesState.capabilities = {
      hasPersonalization: false,
      hasPersona: false
    }

    renderRoute()

    expect(await screen.findByText("Companion unavailable")).toBeInTheDocument()
    expect(mocks.fetchSnapshot).not.toHaveBeenCalled()
  })

  it("registers the companion workspace route in the route registry", () => {
    expect(routeRegistrySource).toMatch(/path:\s*"\/companion"/)
    expect(routeRegistrySource).toContain('labelToken: "option:header.companion"')
  })
})
