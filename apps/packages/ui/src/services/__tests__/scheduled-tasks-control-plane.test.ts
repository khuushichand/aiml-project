import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  bgRequest: vi.fn()
}))

vi.mock("@/services/background-proxy", () => ({
  bgRequest: (...args: unknown[]) => mocks.bgRequest(...args)
}))

import {
  createScheduledTaskReminder,
  deleteScheduledTaskReminder,
  getScheduledTask,
  listScheduledTasks,
  updateScheduledTaskReminder,
  type CreateScheduledTaskReminderPayload,
  type UpdateScheduledTaskReminderPayload
} from "@/services/scheduled-tasks-control-plane"

describe("scheduled-tasks control-plane contract", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("lists normalized scheduled tasks including partial metadata", async () => {
    mocks.bgRequest.mockResolvedValue({
      items: [
        {
          id: "reminder_task:abc",
          primitive: "reminder_task",
          title: "Review notes",
          description: "Check the backlog",
          status: "scheduled",
          enabled: true,
          schedule_summary: "2026-03-21T09:00:00+00:00",
          timezone: null,
          next_run_at: "2026-03-21T09:00:00+00:00",
          last_run_at: null,
          edit_mode: "native",
          manage_url: null,
          source_ref: { task_id: "abc" }
        }
      ],
      total: 1,
      partial: false,
      errors: []
    })

    const response = await listScheduledTasks()

    expect(response.partial).toBe(false)
    expect(response.errors).toEqual([])
    expect(response.items[0]?.source_ref).toMatchObject({ task_id: "abc" })
    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        method: "GET",
        path: "/api/v1/scheduled-tasks"
      })
    )
  })

  it("fetches a single scheduled task by encoded id", async () => {
    mocks.bgRequest.mockResolvedValue({
      id: "reminder_task:abc",
      primitive: "reminder_task",
      title: "Review notes",
      status: "scheduled",
      enabled: true,
      edit_mode: "native",
      source_ref: { task_id: "abc" }
    })

    const response = await getScheduledTask("reminder_task:abc")

    expect(response.id).toBe("reminder_task:abc")
    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        method: "GET",
        path: "/api/v1/scheduled-tasks/reminder_task%3Aabc"
      })
    )
  })

  it("creates reminder tasks with the full typed payload", async () => {
    const payload: CreateScheduledTaskReminderPayload = {
      title: "Follow up",
      body: "Send the update",
      schedule_kind: "one_time",
      run_at: "2026-03-21T10:00:00+00:00",
      enabled: true
    }
    mocks.bgRequest.mockResolvedValue({
      id: "reminder_task:abc",
      primitive: "reminder_task",
      title: "Follow up",
      status: "scheduled",
      enabled: true,
      edit_mode: "native",
      source_ref: { task_id: "abc", schedule_kind: "one_time" }
    })

    const response = await createScheduledTaskReminder(payload)

    expect(response.source_ref).toMatchObject({ task_id: "abc", schedule_kind: "one_time" })
    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        method: "POST",
        path: "/api/v1/scheduled-tasks/reminders",
        body: expect.objectContaining({
          title: "Follow up",
          body: "Send the update",
          schedule_kind: "one_time",
          run_at: "2026-03-21T10:00:00+00:00",
          enabled: true
        })
      })
    )
  })

  it("updates and deletes reminder tasks through reminder routes", async () => {
    const updatePayload: UpdateScheduledTaskReminderPayload = {
      enabled: false,
      title: "Updated follow up"
    }
    mocks.bgRequest
      .mockResolvedValueOnce({
        id: "reminder_task:abc",
        primitive: "reminder_task",
        title: "Updated follow up",
        status: "disabled",
        enabled: false,
        edit_mode: "native",
        source_ref: { task_id: "abc" }
      })
      .mockResolvedValueOnce({ deleted: true })

    const updated = await updateScheduledTaskReminder("abc", updatePayload)
    const deleted = await deleteScheduledTaskReminder("abc")

    expect(updated.enabled).toBe(false)
    expect(deleted.deleted).toBe(true)
    expect(mocks.bgRequest).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({
        method: "PATCH",
        path: "/api/v1/scheduled-tasks/reminders/abc",
        body: expect.objectContaining({
          enabled: false,
          title: "Updated follow up"
        })
      })
    )
    expect(mocks.bgRequest).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        method: "DELETE",
        path: "/api/v1/scheduled-tasks/reminders/abc"
      })
    )
  })
})
