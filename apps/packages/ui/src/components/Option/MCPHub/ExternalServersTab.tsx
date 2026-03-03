import { useEffect, useMemo, useState } from "react"
import { Alert, Button, Empty, List, Space, Tag, Typography } from "antd"

import {
  listExternalServers,
  setExternalServerSecret,
  type McpHubExternalServer
} from "@/services/tldw/mcp-hub"

export const ExternalServersTab = () => {
  const [servers, setServers] = useState<McpHubExternalServer[]>([])
  const [loading, setLoading] = useState(false)
  const [activeServerId, setActiveServerId] = useState<string>("")
  const [secretValue, setSecretValue] = useState("")
  const [saving, setSaving] = useState(false)
  const [configured, setConfigured] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const canSave = useMemo(
    () => activeServerId.trim().length > 0 && secretValue.trim().length > 0 && !saving,
    [activeServerId, secretValue, saving]
  )

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      setLoading(true)
      setErrorMessage(null)
      try {
        const rows = await listExternalServers()
        if (!cancelled) {
          setServers(rows)
          if (!activeServerId && rows.length > 0) {
            setActiveServerId(rows[0].id)
          }
        }
      } catch {
        if (!cancelled) {
          setServers([])
          setErrorMessage("Failed to load external servers.")
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [])

  const handleSaveSecret = async () => {
    if (!canSave) return
    setSaving(true)
    setErrorMessage(null)
    try {
      await setExternalServerSecret(activeServerId, secretValue)
      setSecretValue("")
      setConfigured(true)
    } catch {
      setErrorMessage("Failed to save external server secret.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      <Typography.Text type="secondary">
        External MCP servers are configured here. Secrets are write-only after save.
      </Typography.Text>
      {errorMessage ? <Alert type="error" title={errorMessage} showIcon /> : null}

      {servers.length > 0 ? (
        <Space>
          <label htmlFor="mcp-external-server">Server</label>
          <select
            id="mcp-external-server"
            aria-label="Server"
            value={activeServerId}
            onChange={(event) => setActiveServerId(event.target.value)}
          >
            {servers.map((server) => (
              <option key={server.id} value={server.id}>
                {server.name}
              </option>
            ))}
          </select>
        </Space>
      ) : null}

      <Space direction="vertical" style={{ width: "100%" }}>
        <label htmlFor="mcp-external-secret">Secret</label>
        <input
          id="mcp-external-secret"
          aria-label="Secret"
          type="password"
          value={secretValue}
          onChange={(event) => setSecretValue(event.target.value)}
          placeholder="Paste secret token"
        />
        <Button type="primary" onClick={handleSaveSecret} disabled={!canSave} loading={saving}>
          Save Secret
        </Button>
      </Space>

      {configured ? <Alert type="success" title="Secret configured" showIcon /> : null}

      <List
        bordered
        loading={loading}
        dataSource={servers}
        locale={{ emptyText: <Empty description="No external servers configured" /> }}
        renderItem={(server) => (
          <List.Item>
            <Space>
              <Typography.Text strong>{server.name}</Typography.Text>
              {server.secret_configured ? <Tag color="green">secret configured</Tag> : <Tag>no secret</Tag>}
            </Space>
          </List.Item>
        )}
      />
    </Space>
  )
}
