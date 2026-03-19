import React from "react"
import { CopyOutlined } from "@ant-design/icons"
import { Button, Card, Empty, List, Space, Spin, Tag, Typography, message } from "antd"

import { useCloneWorkspace, useSharedWithMe } from "@/hooks/useSharing"
import {
  getAccessLevelColor,
  getAccessLevelLabel
} from "@/types/sharing"

const { Paragraph, Text } = Typography

export const SharedWithMe: React.FC = () => {
  const { data, isLoading, error } = useSharedWithMe()
  const cloneWorkspace = useCloneWorkspace()
  const shares = Array.isArray(data) ? data : []
  const [messageApi, messageContext] = message.useMessage()

  const _cloneWorkspace = (shareId: number, workspaceName: string) => {
    cloneWorkspace.mutate(
      {
        shareId,
        new_name: `${workspaceName} (Copy)`
      },
      {
        onSuccess: () => {
          messageApi.success(`Cloned "${workspaceName}" into your workspace list.`)
        },
        onError: (cloneError) => {
          messageApi.error(cloneError.message || "Failed to clone shared workspace.")
        }
      }
    )
  }

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
      {messageContext}
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
                onClick={() => _cloneWorkspace(share.share_id, share.workspace_name)}
              >
                Clone
              </Button>
            ]}
          >
            <List.Item.Meta
              title={
                <Space size="small">
                  <span>{share.workspace_name}</span>
                  <Tag color={getAccessLevelColor(String(share.access_level || ""))}>
                    {getAccessLevelLabel(String(share.access_level || "Unknown access"))}
                  </Tag>
                </Space>
              }
              description={
                <Space direction="vertical" size={2}>
                  {share.workspace_description ? (
                    <Text type="secondary">{share.workspace_description}</Text>
                  ) : null}
                  <Text type="secondary">
                    {`Shared by workspace owner (account ${share.owner_user_id})`}
                  </Text>
                </Space>
              }
            />
          </List.Item>
        )}
      />
    </Card>
  )
}
