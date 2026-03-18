import React from "react"
import { CopyOutlined } from "@ant-design/icons"
import { Button, Card, Empty, List, Space, Spin, Tag, Typography } from "antd"

import { useCloneWorkspace, useSharedWithMe } from "@/hooks/useSharing"
import {
  ACCESS_LEVEL_COLORS,
  ACCESS_LEVEL_LABELS
} from "@/types/sharing"

const { Paragraph, Text } = Typography

export const SharedWithMe: React.FC = () => {
  const { data, isLoading, error } = useSharedWithMe()
  const cloneWorkspace = useCloneWorkspace()
  const shares = Array.isArray(data) ? data : []

  if (isLoading) {
    return (
      <div className="flex min-h-[240px] items-center justify-center">
        <Spin size="large" />
      </div>
    )
  }

  if (error) {
    return (
      <Card>
        <Paragraph type="danger">
          {error.message || "Failed to load workspaces shared with you."}
        </Paragraph>
      </Card>
    )
  }

  if (!shares.length) {
    return (
      <Card>
        <Empty description="No shared workspaces available yet." />
      </Card>
    )
  }

  return (
    <Card title="Shared With Me">
      <List
        dataSource={shares}
        renderItem={(share) => (
          <List.Item
            actions={[
              <Button
                key="clone"
                disabled={!share.allow_clone}
                icon={<CopyOutlined />}
                loading={
                  cloneWorkspace.isPending &&
                  cloneWorkspace.variables?.shareId === share.share_id
                }
                onClick={() =>
                  cloneWorkspace.mutate({
                    shareId: share.share_id,
                    new_name: `${share.workspace_name} (Copy)`
                  })
                }
              >
                Clone
              </Button>
            ]}
          >
            <List.Item.Meta
              title={
                <Space size="small">
                  <span>{share.workspace_name}</span>
                  <Tag color={ACCESS_LEVEL_COLORS[share.access_level]}>
                    {ACCESS_LEVEL_LABELS[share.access_level]}
                  </Tag>
                </Space>
              }
              description={
                <Space direction="vertical" size={2}>
                  {share.workspace_description ? (
                    <Text type="secondary">{share.workspace_description}</Text>
                  ) : null}
                  <Text type="secondary">Shared by user #{share.owner_user_id}</Text>
                </Space>
              }
            />
          </List.Item>
        )}
      />
    </Card>
  )
}
