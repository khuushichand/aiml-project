import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  bgRequest: vi.fn()
}))

vi.mock("@/services/background-proxy", () => ({
  bgRequest: (...args: unknown[]) => mocks.bgRequest(...args)
}))

import {
  createCompanionGoal,
  fetchCompanionConversationPrompts,
  fetchCompanionReflectionDetail,
  fetchCompanionWorkspaceSnapshot,
  queueCompanionRebuild,
  recordCompanionCheckIn,
  recordExplicitCompanionCapture,
  setCompanionGoalStatus,
  updateCompanionPreferences
} from "../companion"

describe("companion service", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("loads the companion workspace snapshot and separates reflections from activity", async () => {
    mocks.bgRequest
      .mockResolvedValueOnce({
        items: [
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
          },
          {
            id: "reflection-1",
            event_type: "companion_reflection_generated",
            source_type: "companion_reflection",
            source_id: "daily:2026-03-10",
            surface: "jobs.companion",
            tags: ["reflection"],
            provenance: { source_event_ids: ["activity-1"] },
            metadata: {
              title: "Daily reflection",
              summary: "You revisited project alpha.",
              cadence: "daily",
              evidence: [{ source_id: "42" }]
            },
            created_at: "2026-03-10T13:00:00Z"
          }
        ],
        total: 2,
        limit: 25,
        offset: 0
      })
      .mockResolvedValueOnce({
        items: [
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
        total: 1
      })
      .mockResolvedValueOnce({
        items: [
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
        total: 1
      })
      .mockResolvedValueOnce({
        items: [
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
          },
          {
            id: 12,
            user_id: "1",
            kind: "job_completed",
            title: "Unrelated job",
            message: "Done",
            severity: "info",
            created_at: "2026-03-10T13:05:00Z",
            read_at: null,
            dismissed_at: null
          }
        ],
        total: 2
      })

    const snapshot = await fetchCompanionWorkspaceSnapshot()

    expect(mocks.bgRequest).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({
        path: "/api/v1/companion/activity?limit=25&offset=0",
        method: "GET"
      })
    )
    expect(mocks.bgRequest).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        path: "/api/v1/companion/knowledge?status=active",
        method: "GET"
      })
    )
    expect(mocks.bgRequest).toHaveBeenNthCalledWith(
      3,
      expect.objectContaining({
        path: "/api/v1/companion/goals",
        method: "GET"
      })
    )
    expect(mocks.bgRequest).toHaveBeenNthCalledWith(
      4,
      expect.objectContaining({
        path: "/api/v1/notifications?limit=50&offset=0",
        method: "GET"
      })
    )

    expect(snapshot.activity).toHaveLength(1)
    expect(snapshot.activity[0].id).toBe("activity-1")
    expect(snapshot.reflections).toEqual([
      expect.objectContaining({
        id: "reflection-1",
        summary: "You revisited project alpha.",
        cadence: "daily"
      })
    ])
    expect(snapshot.reflectionNotifications).toEqual([
      expect.objectContaining({
        id: 11,
        kind: "companion_reflection",
        link_id: "reflection-1"
      })
    ])
    expect(snapshot.activeGoalCount).toBe(1)
  })

  it("treats reflection notifications as optional when the inbox endpoint is unavailable", async () => {
    mocks.bgRequest
      .mockResolvedValueOnce({
        items: [],
        total: 0,
        limit: 25,
        offset: 0
      })
      .mockResolvedValueOnce({ items: [], total: 0 })
      .mockResolvedValueOnce({ items: [], total: 0 })
      .mockRejectedValueOnce(new Error("notifications unavailable"))

    const snapshot = await fetchCompanionWorkspaceSnapshot()

    expect(snapshot.reflectionNotifications).toEqual([])
    expect(snapshot.reflections).toEqual([])
  })

  it("creates manual goals through the companion goals endpoint", async () => {
    mocks.bgRequest.mockResolvedValue({
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

    await createCompanionGoal({
      title: "Capture a weekly review",
      goal_type: "manual"
    })

    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/companion/goals",
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: {
          title: "Capture a weekly review",
          goal_type: "manual"
        }
      })
    )
  })

  it("loads reflection detail with follow-up prompt payloads", async () => {
    mocks.bgRequest.mockResolvedValue({
      id: "reflection-1",
      title: "Daily reflection",
      cadence: "daily",
      summary: "You revisited project alpha.",
      evidence: [{ source_id: "42" }],
      provenance: {
        source_event_ids: ["activity-1"]
      },
      created_at: "2026-03-10T13:00:00Z",
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
      activity_events: [],
      knowledge_cards: [],
      goals: []
    })

    const detail = await fetchCompanionReflectionDetail("reflection-1")

    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/companion/reflections/reflection-1",
        method: "GET"
      })
    )
    expect(detail.follow_up_prompts[0].prompt_text).toBe(
      "What is the next concrete step for project alpha?"
    )
  })

  it("loads companion conversation prompts through the dedicated endpoint", async () => {
    mocks.bgRequest.mockResolvedValue({
      prompt_source_kind: "reflection",
      prompt_source_id: "reflection-1",
      prompts: [
        {
          prompt_id: "prompt-1",
          label: "Next concrete step",
          prompt_text: "What is the next concrete step for project alpha?",
          prompt_type: "clarify_priority",
          source_reflection_id: "reflection-1",
          source_evidence_ids: ["activity-1"]
        }
      ]
    })

    const payload = await fetchCompanionConversationPrompts("resume backlog review")

    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/companion/conversation-prompts?query=resume+backlog+review",
        method: "GET"
      })
    )
    expect(payload.prompts[0].label).toBe("Next concrete step")
  })

  it("records explicit companion capture through the activity endpoint", async () => {
    mocks.bgRequest.mockResolvedValue({
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
      created_at: "2026-03-10T14:00:00Z"
    })

    await recordExplicitCompanionCapture({
      event_type: "extension.selection_saved",
      source_type: "browser_selection",
      source_id: "capture-1",
      surface: "extension.sidepanel",
      dedupe_key: "extension.selection_saved:capture-1",
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
      }
    })

    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/companion/activity",
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: {
          event_type: "extension.selection_saved",
          source_type: "browser_selection",
          source_id: "capture-1",
          surface: "extension.sidepanel",
          dedupe_key: "extension.selection_saved:capture-1",
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
          }
        }
      })
    )
  })

  it("records manual check-ins through the dedicated companion endpoint", async () => {
    mocks.bgRequest.mockResolvedValue({
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

    await recordCompanionCheckIn({
      title: "Morning reset",
      summary: "Re-focused on the companion capture backlog before lunch.",
      tags: ["planning", "focus"]
    })

    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/companion/check-ins",
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: {
          title: "Morning reset",
          summary: "Re-focused on the companion capture backlog before lunch.",
          tags: ["planning", "focus"]
        }
      })
    )
  })

  it("patches goal status through the companion goals endpoint", async () => {
    mocks.bgRequest.mockResolvedValue({
      id: "goal-1",
      title: "Finish queue",
      description: "Read three saved papers.",
      goal_type: "reading_backlog",
      config: { target_count: 3 },
      progress: { completed_count: 1 },
      status: "paused",
      created_at: "2026-03-10T09:00:00Z",
      updated_at: "2026-03-10T10:05:00Z"
    })

    await setCompanionGoalStatus("goal-1", "paused")

    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/companion/goals/goal-1",
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: { status: "paused" }
      })
    )
  })

  it("updates companion reflection preferences through personalization preferences", async () => {
    mocks.bgRequest.mockResolvedValue({
      enabled: true,
      companion_reflections_enabled: true,
      companion_daily_reflections_enabled: false,
      companion_weekly_reflections_enabled: true,
      proactive_enabled: true,
      updated_at: "2026-03-10T15:00:00Z"
    })

    await updateCompanionPreferences({
      companion_daily_reflections_enabled: false
    })

    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/personalization/preferences",
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: {
          companion_daily_reflections_enabled: false
        }
      })
    )
  })

  it("loads a reflection detail payload through the provenance endpoint", async () => {
    mocks.bgRequest.mockResolvedValue({
      id: "reflection-1",
      title: "Daily reflection",
      cadence: "daily",
      summary: "You revisited project alpha.",
      evidence: [],
      provenance: { source_event_ids: ["activity-1"] },
      created_at: "2026-03-10T13:00:00Z",
      activity_events: [],
      knowledge_cards: [],
      goals: []
    })

    await fetchCompanionReflectionDetail("reflection-1")

    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/companion/reflections/reflection-1",
        method: "GET"
      })
    )
  })

  it("queues a scoped rebuild through the companion lifecycle endpoint", async () => {
    mocks.bgRequest.mockResolvedValue({
      status: "queued",
      scope: "knowledge",
      job_id: 51,
      job_uuid: "job-uuid-51"
    })

    await queueCompanionRebuild("knowledge")

    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/companion/rebuild",
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: {
          scope: "knowledge"
        }
      })
    )
  })
})
