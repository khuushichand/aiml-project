import React from "react"
import { Drawer, Descriptions, Space, Tag, Typography } from "antd"
import type { IntegrationConnection } from "@/services/integrations-control-plane"

type IntegrationConnectionDrawerProps = {
  open: boolean
  connection: IntegrationConnection | null
  onClose: () => void
}

const formatJson = (value: Record<string, unknown>): string => {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return "{}"
  }
}

export const IntegrationConnectionDrawer: React.FC<IntegrationConnectionDrawerProps> = ({
  open,
  connection,
  onClose
}) => {
  return (
    <Drawer
      title={connection?.display_name ?? "Connection details"}
      open={open}
      onClose={onClose}
      width={520}
      destroyOnClose
    >
      {connection ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 16, width: "100%" }}>
          <Descriptions size="small" column={1} bordered>
            <Descriptions.Item label="Provider">{connection.provider}</Descriptions.Item>
            <Descriptions.Item label="Scope">{connection.scope}</Descriptions.Item>
            <Descriptions.Item label="Status">
              <Tag color={connection.enabled ? "green" : "default"}>{connection.status}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="Enabled">
              <Tag color={connection.enabled ? "green" : "default"}>
                {connection.enabled ? "yes" : "no"}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="Connected at">
              {connection.connected_at ? new Date(connection.connected_at).toLocaleString() : "—"}
            </Descriptions.Item>
            <Descriptions.Item label="Updated at">
              {connection.updated_at ? new Date(connection.updated_at).toLocaleString() : "—"}
            </Descriptions.Item>
          </Descriptions>

          <div>
            <Typography.Title level={5}>Actions</Typography.Title>
            <Space wrap>
              {connection.actions.length > 0 ? (
                connection.actions.map((action) => <Tag key={action}>{action}</Tag>)
              ) : (
                <Typography.Text type="secondary">No actions available.</Typography.Text>
              )}
            </Space>
          </div>

          <div>
            <Typography.Title level={5}>Metadata</Typography.Title>
            <pre style={{ whiteSpace: "pre-wrap", wordBreak: "break-word", margin: 0 }}>
              {formatJson(connection.metadata)}
            </pre>
          </div>
        </div>
      ) : null}
    </Drawer>
  )
}

export default IntegrationConnectionDrawer
