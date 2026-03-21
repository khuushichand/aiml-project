import React, { useEffect } from "react"
import { Button, Card, Form, Input, Select, Space, Switch } from "antd"
import type {
  CreateScheduledTaskReminderPayload,
  ScheduledTask,
  UpdateScheduledTaskReminderPayload
} from "@/services/scheduled-tasks-control-plane"

type ReminderTaskEditorValues = {
  title: string
  body?: string | null
  schedule_kind: "one_time" | "recurring"
  run_at?: string | null
  cron?: string | null
  timezone?: string | null
  enabled: boolean
}

type ReminderTaskEditorProps = {
  open: boolean
  task: ScheduledTask | null
  saving?: boolean
  onClose: () => void
  onSubmit: (payload: CreateScheduledTaskReminderPayload | UpdateScheduledTaskReminderPayload) => Promise<void> | void
}

const taskToValues = (task: ScheduledTask | null): ReminderTaskEditorValues => {
  const sourceRef = (task?.source_ref ?? {}) as Record<string, unknown>
  return {
    title: task?.title ?? "",
    body: typeof task?.description === "string" ? task.description : "",
    schedule_kind: sourceRef.schedule_kind === "recurring" ? "recurring" : "one_time",
    run_at: typeof sourceRef.run_at === "string" ? sourceRef.run_at : "",
    cron: typeof sourceRef.cron === "string" ? sourceRef.cron : "",
    timezone: typeof sourceRef.timezone === "string" ? sourceRef.timezone : "",
    enabled: Boolean(task?.enabled)
  }
}

export const ReminderTaskEditor: React.FC<ReminderTaskEditorProps> = ({
  open,
  task,
  saving,
  onClose,
  onSubmit
}) => {
  const [form] = Form.useForm<ReminderTaskEditorValues>()

  useEffect(() => {
    if (open) {
      form.setFieldsValue(taskToValues(task))
    }
  }, [form, open, task])

  if (!open) {
    return null
  }

  const handleFinish = async () => {
    const values = await form.validateFields()
    const payload =
      values.schedule_kind === "one_time"
        ? {
            title: values.title.trim(),
            body: values.body?.trim() || null,
            schedule_kind: "one_time" as const,
            run_at: values.run_at?.trim() || null,
            timezone: values.timezone?.trim() || null,
            enabled: Boolean(values.enabled)
          }
        : {
            title: values.title.trim(),
            body: values.body?.trim() || null,
            schedule_kind: "recurring" as const,
            cron: values.cron?.trim() || null,
            timezone: values.timezone?.trim() || null,
            enabled: Boolean(values.enabled)
          }

    await onSubmit(payload)
  }

  return (
    <Card title={task ? "Edit reminder task" : "Create reminder task"} style={{ marginTop: 16 }}>
      <Form form={form} layout="vertical">
        <Form.Item label="Title" name="title" rules={[{ required: true, message: "Title is required" }]}>
          <Input />
        </Form.Item>
        <Form.Item label="Body" name="body">
          <Input.TextArea rows={4} />
        </Form.Item>
        <Form.Item
          label="Schedule kind"
          name="schedule_kind"
          rules={[{ required: true, message: "Schedule kind is required" }]}
        >
          <Select
            options={[
              { value: "one_time", label: "One time" },
              { value: "recurring", label: "Recurring" }
            ]}
          />
        </Form.Item>
        <Form.Item label="Run at" name="run_at">
          <Input placeholder="2026-03-21T10:00:00+00:00" />
        </Form.Item>
        <Form.Item label="Cron" name="cron">
          <Input placeholder="0 9 * * *" />
        </Form.Item>
        <Form.Item label="Timezone" name="timezone">
          <Input placeholder="UTC" />
        </Form.Item>
        <Form.Item label="Enabled" name="enabled" valuePropName="checked">
          <Switch />
        </Form.Item>
        <Space>
          <Button type="primary" onClick={() => void handleFinish()} loading={saving}>
            Save Reminder Task
          </Button>
          <Button onClick={onClose}>Cancel</Button>
        </Space>
      </Form>
    </Card>
  )
}

export default ReminderTaskEditor
