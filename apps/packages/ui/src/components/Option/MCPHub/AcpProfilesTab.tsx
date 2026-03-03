import { useEffect, useMemo, useState } from "react"
import { Button, Card, Empty, List, Space, Tag, Typography } from "antd"

import { createAcpProfile, listAcpProfiles, type McpHubProfile } from "@/services/tldw/mcp-hub"

export const AcpProfilesTab = () => {
  const [profiles, setProfiles] = useState<McpHubProfile[]>([])
  const [loading, setLoading] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [name, setName] = useState("")
  const [saving, setSaving] = useState(false)
  const canSave = useMemo(() => name.trim().length > 0 && !saving, [name, saving])

  const loadProfiles = async () => {
    setLoading(true)
    try {
      const rows = await listAcpProfiles()
      setProfiles(Array.isArray(rows) ? rows : [])
    } catch {
      setProfiles([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadProfiles()
  }, [])

  const handleCreate = async () => {
    if (!canSave) return
    setSaving(true)
    try {
      await createAcpProfile({
        name: name.trim(),
        owner_scope_type: "global",
        profile: {}
      })
      setCreateOpen(false)
      setName("")
      await loadProfiles()
    } finally {
      setSaving(false)
    }
  }

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      <Typography.Text type="secondary">
        ACP profiles define reusable MCP execution defaults.
      </Typography.Text>

      <Space>
        <Button type="primary" onClick={() => setCreateOpen(true)}>
          Create Profile
        </Button>
      </Space>

      {createOpen ? (
        <Card title="Create ACP Profile">
          <Space direction="vertical" style={{ width: "100%" }}>
            <label htmlFor="mcp-profile-name">Profile Name</label>
            <input
              id="mcp-profile-name"
              aria-label="Profile Name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="default-dev"
            />
            <Space>
              <Button type="primary" onClick={handleCreate} disabled={!canSave} loading={saving}>
                Save Profile
              </Button>
              <Button
                onClick={() => {
                  setCreateOpen(false)
                  setName("")
                }}
              >
                Cancel
              </Button>
            </Space>
          </Space>
        </Card>
      ) : null}

      <List
        bordered
        loading={loading}
        dataSource={profiles}
        locale={{ emptyText: <Empty description="No ACP profiles yet" /> }}
        renderItem={(profile) => (
          <List.Item>
            <Space direction="vertical" size={2}>
              <Typography.Text strong>{profile.name}</Typography.Text>
              <Space size={6}>
                <Tag>{profile.owner_scope_type}</Tag>
                {profile.is_active ? <Tag color="green">active</Tag> : <Tag>inactive</Tag>}
              </Space>
            </Space>
          </List.Item>
        )}
      />
    </Space>
  )
}
