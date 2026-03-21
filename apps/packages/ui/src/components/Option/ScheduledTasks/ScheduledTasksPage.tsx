import React, { useState } from "react"
import { Alert, Spin, Typography, message } from "antd"
import { useQuery } from "@tanstack/react-query"
import {
  createScheduledTaskReminder,
  deleteScheduledTaskReminder,
  listScheduledTasks,
  updateScheduledTaskReminder,
  type ScheduledTask,
  type CreateScheduledTaskReminderPayload,
  type UpdateScheduledTaskReminderPayload
} from "@/services/scheduled-tasks-control-plane"
import { ScheduledTaskTable } from "./ScheduledTaskTable"
import { ReminderTaskEditor } from "./ReminderTaskEditor"

export const ScheduledTasksPage: React.FC = () => {
  const [editorOpen, setEditorOpen] = useState(false)
  const [editingTask, setEditingTask] = useState<ScheduledTask | null>(null)
  const [saving, setSaving] = useState(false)

  const tasksQuery = useQuery({
    queryKey: ["scheduled-tasks"],
    queryFn: listScheduledTasks
  })

  const tasks = tasksQuery.data?.items ?? []

  const openCreateReminder = () => {
    setEditingTask(null)
    setEditorOpen(true)
  }

  const openEditReminder = (task: ScheduledTask) => {
    setEditingTask(task)
    setEditorOpen(true)
  }

  const closeEditor = () => {
    setEditorOpen(false)
    setEditingTask(null)
  }

  const refreshTasks = async () => {
    await tasksQuery.refetch()
  }

  const handleSubmit = async (
    payload: CreateScheduledTaskReminderPayload | UpdateScheduledTaskReminderPayload
  ) => {
    setSaving(true)
    try {
      if (editingTask) {
        await updateScheduledTaskReminder(editingTask.id, payload as UpdateScheduledTaskReminderPayload)
        message.success("Reminder task updated")
      } else {
        await createScheduledTaskReminder(payload as CreateScheduledTaskReminderPayload)
        message.success("Reminder task created")
      }
      closeEditor()
      await refreshTasks()
    } catch (error: any) {
      message.error(error?.message || "Unable to save reminder task")
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteReminder = async (task: ScheduledTask) => {
    try {
      await deleteScheduledTaskReminder(task.id)
      message.success("Reminder task deleted")
      await refreshTasks()
    } catch (error: any) {
      message.error(error?.message || "Unable to delete reminder task")
    }
  }

  const partialErrors = tasksQuery.data?.errors ?? []

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 p-6">
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <Typography.Title level={2} style={{ marginBottom: 0 }}>
          Scheduled tasks
        </Typography.Title>
        <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
          Review reminder tasks here. Watchlist jobs remain managed from Watchlists.
        </Typography.Paragraph>
      </div>

      {tasksQuery.isLoading ? <Spin /> : null}
      {tasksQuery.isError ? (
        <Alert
          type="error"
          showIcon
          title="Unable to load scheduled tasks"
          description={tasksQuery.error instanceof Error ? tasksQuery.error.message : "The scheduled tasks overview could not be loaded."}
        />
      ) : null}
      {tasksQuery.data?.partial ? (
        <Alert
          type="warning"
          showIcon
          title="Some scheduled tasks could not be loaded"
          description={partialErrors.length ? partialErrors.join(", ") : "The overview is partially available."}
        />
      ) : null}

      <ScheduledTaskTable
        tasks={tasks}
        onCreateReminder={openCreateReminder}
        onEditReminder={openEditReminder}
        onDeleteReminder={handleDeleteReminder}
      />

      <ReminderTaskEditor
        open={editorOpen}
        task={editingTask}
        saving={saving}
        onClose={closeEditor}
        onSubmit={handleSubmit}
      />
    </div>
  )
}

export default ScheduledTasksPage
