/**
 * Scheduled tasks control-plane API client.
 */

import { bgRequest } from "@/services/background-proxy"
import { toAllowedPath } from "@/services/tldw/path-utils"

export type ScheduledTaskPrimitive = "reminder_task" | "watchlist_job"
export type ScheduledTaskEditMode = "native" | "external"
export type ReminderScheduleKind = "one_time" | "recurring"

export interface ScheduledTask {
  id: string
  primitive: ScheduledTaskPrimitive
  title: string
  description?: string | null
  status: string
  enabled: boolean
  schedule_summary?: string | null
  timezone?: string | null
  next_run_at?: string | null
  last_run_at?: string | null
  edit_mode: ScheduledTaskEditMode
  manage_url?: string | null
  source_ref: Record<string, unknown>
}

export interface ScheduledTaskListResponse {
  items: ScheduledTask[]
  total: number
  partial: boolean
  errors: string[]
}

export interface ScheduledTaskDeleteResponse {
  deleted: boolean
}

export interface CreateScheduledTaskReminderPayload {
  title: string
  body?: string | null
  schedule_kind: ReminderScheduleKind
  run_at?: string | null
  cron?: string | null
  timezone?: string | null
  link_type?: string | null
  link_id?: string | null
  link_url?: string | null
  enabled?: boolean
}

export interface UpdateScheduledTaskReminderPayload {
  title?: string | null
  body?: string | null
  schedule_kind?: ReminderScheduleKind | null
  run_at?: string | null
  cron?: string | null
  timezone?: string | null
  link_type?: string | null
  link_id?: string | null
  link_url?: string | null
  enabled?: boolean | null
}

export async function listScheduledTasks(): Promise<ScheduledTaskListResponse> {
  return await bgRequest<ScheduledTaskListResponse>({
    path: "/api/v1/scheduled-tasks",
    method: "GET"
  })
}

export async function getScheduledTask(taskId: string): Promise<ScheduledTask> {
  return await bgRequest<ScheduledTask>({
    path: toAllowedPath(`/api/v1/scheduled-tasks/${encodeURIComponent(taskId)}`),
    method: "GET"
  })
}

export async function createScheduledTaskReminder(
  payload: CreateScheduledTaskReminderPayload
): Promise<ScheduledTask> {
  return await bgRequest<ScheduledTask>({
    path: "/api/v1/scheduled-tasks/reminders",
    method: "POST",
    body: payload
  })
}

export async function updateScheduledTaskReminder(
  taskId: string,
  payload: UpdateScheduledTaskReminderPayload
): Promise<ScheduledTask> {
  return await bgRequest<ScheduledTask>({
    path: toAllowedPath(`/api/v1/scheduled-tasks/reminders/${encodeURIComponent(taskId)}`),
    method: "PATCH",
    body: payload
  })
}

export async function deleteScheduledTaskReminder(taskId: string): Promise<ScheduledTaskDeleteResponse> {
  return await bgRequest<ScheduledTaskDeleteResponse>({
    path: toAllowedPath(`/api/v1/scheduled-tasks/reminders/${encodeURIComponent(taskId)}`),
    method: "DELETE"
  })
}
