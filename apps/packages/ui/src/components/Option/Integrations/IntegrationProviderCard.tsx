import React from "react"
import { Button, Card, Empty, List, Space, Tag, Typography } from "antd"
import type {
  IntegrationConnection,
  IntegrationProvider,
  IntegrationScope
} from "@/services/integrations-control-plane"

type IntegrationProviderCardProps = {
  title: string
  provider: IntegrationProvider
  scope: IntegrationScope
  connections: IntegrationConnection[]
  onInspect?: (connection: IntegrationConnection) => void
}

const providerEmoji: Record<IntegrationProvider, string> = {
  slack: "Slack",
  discord: "Discord",
  telegram: "Telegram"
}

const statusColor = (status: IntegrationConnection["status"]): string => {
  if (status === "connected") return "green"
  if (status === "disabled") return "default"
  if (status === "degraded" || status === "needs_config") return "orange"
  return "red"
}

export const IntegrationProviderCard: React.FC<IntegrationProviderCardProps> = ({
  title,
  provider,
  scope,
  connections,
  onInspect
}) => {
  const hasConnections = connections.length > 0

  return (
    <Card
      title={
        <Space size="small" wrap>
          <span>{title}</span>
          <Tag>{scope}</Tag>
          <Tag color={hasConnections ? "green" : "default"}>{connections.length} connections</Tag>
        </Space>
      }
      className="h-full"
    >
      {hasConnections ? (
        <List
          dataSource={connections}
          split
          renderItem={(item) => (
            <List.Item
              actions={
                onInspect
                  ? [<Button key="inspect" size="small" onClick={() => onInspect(item)}>Manage</Button>]
                  : undefined
              }
            >
              <List.Item.Meta
                title={
                  <Space wrap>
                    <Typography.Text strong>{item.display_name}</Typography.Text>
                    <Tag color={statusColor(item.status)}>{item.status}</Tag>
                    <Tag color={item.enabled ? "green" : "default"}>
                      {item.enabled ? "enabled" : "disabled"}
                    </Tag>
                  </Space>
                }
                description={
                  <Space wrap size="small">
                    <Tag>{providerEmoji[provider]}</Tag>
                    {item.connected_at ? <Typography.Text type="secondary">Connected {new Date(item.connected_at).toLocaleString()}</Typography.Text> : null}
                    {item.actions?.length
                      ? item.actions.map((action) => <Tag key={action}>{action}</Tag>)
                      : null}
                  </Space>
                }
              />
            </List.Item>
          )}
        />
      ) : (
        <Empty
          description={`No ${title.toLowerCase()} connections found`}
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      )}
    </Card>
  )
}

export default IntegrationProviderCard
