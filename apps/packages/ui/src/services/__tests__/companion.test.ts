import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  bgRequest: vi.fn()
}))

vi.mock("@/services/background-proxy", () => ({
  bgRequest: (...args: unknown[]) => mocks.bgRequest(...args)
}))

import {
  createCompanionGoal,
  fetchCompanionWorkspaceSnapshot,
  recordExplicitCompanionCapture,
  setCompanionGoalStatus
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
})
