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
  fetchProfile: vi.fn(),
  updateOptIn: vi.fn(),
  updatePreferences: vi.fn(),
  setGoalStatus: vi.fn(),
  createGoal: vi.fn(),
  recordCheckIn: vi.fn(),
  fetchReflectionDetail: vi.fn(),
  purgeScope: vi.fn(),
  rebuildScope: vi.fn()
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
  fetchPersonalizationProfile: (...args: unknown[]) => mocks.fetchProfile(...args),
  updatePersonalizationOptIn: (...args: unknown[]) => mocks.updateOptIn(...args),
  updateCompanionPreferences: (...args: unknown[]) => mocks.updatePreferences(...args),
  fetchCompanionWorkspaceSnapshot: (...args: unknown[]) =>
    mocks.fetchSnapshot(...args),
  setCompanionGoalStatus: (...args: unknown[]) => mocks.setGoalStatus(...args),
  createCompanionGoal: (...args: unknown[]) => mocks.createGoal(...args),
  recordCompanionCheckIn: (...args: unknown[]) => mocks.recordCheckIn(...args),
  fetchCompanionReflectionDetail: (...args: unknown[]) =>
    mocks.fetchReflectionDetail(...args),
  purgeCompanionScope: (...args: unknown[]) => mocks.purgeScope(...args),
  queueCompanionRebuild: (...args: unknown[]) => mocks.rebuildScope(...args)
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
    mocks.fetchProfile.mockResolvedValue({
      enabled: true,
      updated_at: "2026-03-10T08:00:00Z"
    })
    mocks.updateOptIn.mockResolvedValue({
      enabled: true,
      updated_at: "2026-03-10T15:00:00Z"
    })
    mocks.updatePreferences.mockResolvedValue({
      enabled: true,
      proactive_enabled: true,
      companion_reflections_enabled: true,
      companion_daily_reflections_enabled: false,
      companion_weekly_reflections_enabled: true,
      updated_at: "2026-03-10T15:00:00Z"
    })
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
    mocks.fetchReflectionDetail.mockResolvedValue({
      id: "reflection-1",
      title: "Daily reflection",
      cadence: "daily",
      summary: "You revisited project alpha.",
      delivery_decision: "delivered",
      delivery_reason: "meaningful_signal",
      theme_key: "project-alpha",
      signal_strength: 3,
      follow_up_prompts: [
        {
          prompt_id: "prompt-1",
          label: "Next concrete step",
          prompt_text: "What is the next concrete step for project alpha?",
          prompt_type: "clarify_priority",
          source_reflection_id: "reflection-1",
          source_evidence_ids: ["activity-1"]
        }
      ],
      evidence: [],
      provenance: {
        source_event_ids: ["activity-1"],
        knowledge_card_ids: ["knowledge-1"],
        goal_ids: ["goal-1"]
      },
      created_at: "2026-03-10T13:00:00Z",
      activity_events: [activeSnapshot.activity[0]],
      knowledge_cards: [activeSnapshot.knowledge[0]],
      goals: [activeSnapshot.goals[0]]
    })
    mocks.purgeScope.mockResolvedValue({
      status: "completed",
      scope: "knowledge",
      deleted_counts: { knowledge: 1 }
    })
    mocks.rebuildScope.mockResolvedValue({
      status: "queued",
      scope: "knowledge",
      job_id: 51,
      job_uuid: "job-uuid-51"
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
    expect(screen.getByRole("link", { name: "Open conversation" })).toHaveAttribute(
      "href",
      "/companion/conversation"
    )
    expect(screen.queryByRole("link", { name: "Open persona" })).not.toBeInTheDocument()
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

  it("shows a consent screen when personalization is available but not enabled", async () => {
    mocks.fetchProfile.mockResolvedValue({
      enabled: false,
      updated_at: "2026-03-10T08:00:00Z"
    })

    renderRoute()

    expect(await screen.findByTestId("companion-consent-required")).toBeInTheDocument()
    expect(
      screen.getByText("Enable personalization before using Companion.")
    ).toBeInTheDocument()
    expect(mocks.fetchSnapshot).not.toHaveBeenCalled()
  })

  it("enables personalization from the consent screen and then loads the workspace", async () => {
    mocks.fetchProfile
      .mockResolvedValueOnce({
        enabled: false,
        updated_at: "2026-03-10T08:00:00Z"
      })
      .mockResolvedValueOnce({
        enabled: true,
        updated_at: "2026-03-10T15:00:00Z"
      })

    renderRoute()

    await screen.findByTestId("companion-consent-required")
    fireEvent.click(screen.getByRole("button", { name: "Enable Companion" }))

    await waitFor(() => {
      expect(mocks.updateOptIn).toHaveBeenCalledWith(true)
    })
    expect(await screen.findByTestId("companion-page")).toBeInTheDocument()
    expect(mocks.fetchSnapshot).toHaveBeenCalled()
  })

  it("shows companion settings and persists reflection toggles", async () => {
    renderRoute()

    expect(await screen.findByRole("heading", { name: "Settings" })).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText("Daily reflections"))

    await waitFor(() => {
      expect(mocks.updatePreferences).toHaveBeenCalledWith(
        expect.objectContaining({ companion_daily_reflections_enabled: false })
      )
    })
  })

  it("opens a provenance drawer for a reflection", async () => {
    renderRoute()

    await screen.findByText("You revisited project alpha.")
    fireEvent.click(screen.getByRole("button", { name: "View reflection provenance" }))

    expect(await screen.findByText("Source event ids")).toBeInTheDocument()
    expect(screen.getByText("activity-1")).toBeInTheDocument()
    expect(screen.getByText("knowledge-1")).toBeInTheDocument()
  })

  it("shows follow-up prompts when a reflection is opened", async () => {
    renderRoute()

    await screen.findByText("You revisited project alpha.")
    fireEvent.click(screen.getByRole("button", { name: "View reflection provenance" }))

    expect(await screen.findByText("Follow-up prompts")).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Next concrete step" })
    ).toBeInTheDocument()
  })

  it("does not render standalone prompt chips on the default workspace surface", async () => {
    renderRoute()

    await screen.findByText("You revisited project alpha.")
    expect(screen.queryByText("Follow-up prompts")).not.toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: "Next concrete step" })
    ).not.toBeInTheDocument()
  })

  it("registers the companion workspace route in the route registry", () => {
    expect(routeRegistrySource).toMatch(/path:\s*"\/companion"/)
    expect(routeRegistrySource).toContain('labelToken: "option:header.companion"')
  })
})
