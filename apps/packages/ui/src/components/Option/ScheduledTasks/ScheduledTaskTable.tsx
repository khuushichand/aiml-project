import React from "react"
import { Button, Space, Table, Tag, Typography } from "antd"
import type { ColumnsType } from "antd/es/table"
import type { ScheduledTask } from "@/services/scheduled-tasks-control-plane"

export interface ScheduledTaskTableRowActionContext {
  task: ScheduledTask
}

export interface ScheduledTaskTableProps {
  tasks: ScheduledTask[]
  onCreateReminder: () => void
  onEditReminder: (task: ScheduledTask) => void
  onDeleteReminder: (task: ScheduledTask) => void
}

const isNativeReminder = (task: ScheduledTask): boolean => task.edit_mode === "native"

export const ScheduledTaskTable: React.FC<ScheduledTaskTableProps> = ({
  tasks,
  onCreateReminder,
  onEditReminder,
  onDeleteReminder
}) => {
  const columns: ColumnsType<ScheduledTask> = [
    {
      title: "Task",
      dataIndex: "title",
      key: "title",
      render: (_, task) => (
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <Typography.Text strong>{task.title}</Typography.Text>
          <Typography.Text type="secondary">{task.description || task.schedule_summary || "—"}</Typography.Text>
        </div>
      )
    },
    {
      title: "Mode",
      key: "mode",
      render: (_, task) => (
        <Tag color={isNativeReminder(task) ? "blue" : "gold"}>
          {isNativeReminder(task) ? "Native" : "External managed"}
        </Tag>
      )
    },
    {
      title: "Schedule",
      key: "schedule",
      render: (_, task) => (
        <div style={{ display: "flex", flexDirection: "column" }}>
          <Typography.Text>{task.schedule_summary || "Manual"}</Typography.Text>
          <Typography.Text type="secondary">
            {task.timezone ? `Timezone: ${task.timezone}` : "No timezone"}
          </Typography.Text>
        </div>
      )
    },
    {
      title: "Status",
      key: "status",
      render: (_, task) => (
        <Tag color={task.enabled ? "green" : "default"}>{task.status}</Tag>
      )
    },
    {
      title: "Actions",
      key: "actions",
      render: (_, task) =>
        isNativeReminder(task) ? (
          <Space wrap>
            <Button size="small" onClick={() => onEditReminder(task)}>
              Edit
            </Button>
            <Button size="small" danger onClick={() => onDeleteReminder(task)}>
              Delete
            </Button>
          </Space>
        ) : (
          <Space wrap>
            <Button
              size="small"
              type="link"
              href={task.manage_url || "/watchlists?tab=jobs"}
              target="_self"
            >
              Manage in Watchlists
            </Button>
          </Space>
        )
    }
  ]

  return (
    <Table<ScheduledTask>
      rowKey="id"
      columns={columns}
      dataSource={tasks}
      pagination={false}
      title={() => (
        <Space style={{ width: "100%", justifyContent: "space-between" }}>
          <Typography.Title level={4} style={{ margin: 0 }}>
            Scheduled tasks
          </Typography.Title>
          <Button type="primary" onClick={onCreateReminder}>
            Create Reminder Task
          </Button>
        </Space>
      )}
    />
  )
}

export default ScheduledTaskTable
