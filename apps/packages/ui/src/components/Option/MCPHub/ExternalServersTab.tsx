import { useEffect, useMemo, useState } from "react"
import { Alert, Button, Card, Checkbox, Empty, List, Space, Tag, Typography } from "antd"

import {
  createExternalServer,
  deleteExternalServer,
  importExternalServer,
  listExternalServers,
  setExternalServerSecret,
  updateExternalServer,
  type McpHubExternalServer
} from "@/services/tldw/mcp-hub"

import { getManagedExternalServers } from "./policyHelpers"

export const ExternalServersTab = () => {
  const [servers, setServers] = useState<McpHubExternalServer[]>([])
  const [loading, setLoading] = useState(false)
  const [activeServerId, setActiveServerId] = useState<string>("")
  const [secretValue, setSecretValue] = useState("")
  const [saving, setSaving] = useState(false)
  const [importingServerId, setImportingServerId] = useState<string | null>(null)
  const [configured, setConfigured] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [serverFormOpen, setServerFormOpen] = useState(false)
  const [editingServerId, setEditingServerId] = useState<string | null>(null)
  const [serverIdValue, setServerIdValue] = useState("")
  const [serverNameValue, setServerNameValue] = useState("")
  const [transportValue, setTransportValue] = useState("stdio")
  const [ownerScopeType, setOwnerScopeType] = useState<"global" | "org" | "team" | "user">("global")
  const [enabledValue, setEnabledValue] = useState(true)
  const [configText, setConfigText] = useState("{}")
  const [serverSaving, setServerSaving] = useState(false)
  const managedServers = useMemo(() => getManagedExternalServers(servers), [servers])

  const canSave = useMemo(
    () => activeServerId.trim().length > 0 && secretValue.trim().length > 0 && !saving,
    [activeServerId, secretValue, saving]
  )

  const loadServers = async () => {
    setLoading(true)
    setErrorMessage(null)
    try {
      const rows = await listExternalServers()
      setServers(Array.isArray(rows) ? rows : [])
      const managedRows = getManagedExternalServers(rows)
      if (managedRows.some((server) => server.id === activeServerId)) {
        return
      }
      setActiveServerId(managedRows[0]?.id || "")
    } catch {
      setServers([])
      setActiveServerId("")
      setErrorMessage("Failed to load external servers.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadServers()
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

  const handleImport = async (serverId: string) => {
    setImportingServerId(serverId)
    setErrorMessage(null)
    try {
      const imported = await importExternalServer(serverId)
      setConfigured(false)
      await loadServers()
      setActiveServerId(imported.id)
    } catch {
      setErrorMessage("Failed to import legacy external server.")
    } finally {
      setImportingServerId(null)
    }
  }

  const resetServerForm = () => {
    setServerFormOpen(false)
    setEditingServerId(null)
    setServerIdValue("")
    setServerNameValue("")
    setTransportValue("stdio")
    setOwnerScopeType("global")
    setEnabledValue(true)
    setConfigText("{}")
    setServerSaving(false)
  }

  const openCreateForm = () => {
    resetServerForm()
    setServerFormOpen(true)
  }

  const openEditForm = (server: McpHubExternalServer) => {
    setServerFormOpen(true)
    setEditingServerId(server.id)
    setServerIdValue(server.id)
    setServerNameValue(server.name)
    setTransportValue(server.transport || "stdio")
    setOwnerScopeType(server.owner_scope_type)
    setEnabledValue(Boolean(server.enabled))
    setConfigText(JSON.stringify(server.config || {}, null, 2))
  }

  const handleSaveServer = async () => {
    if (!serverNameValue.trim() || !transportValue.trim()) {
      setErrorMessage("Server name and transport are required.")
      return
    }
    if (!editingServerId && !serverIdValue.trim()) {
      setErrorMessage("Server id is required.")
      return
    }
    let parsedConfig: Record<string, unknown> = {}
    try {
      parsedConfig = JSON.parse(configText || "{}") as Record<string, unknown>
      if (!parsedConfig || typeof parsedConfig !== "object" || Array.isArray(parsedConfig)) {
        throw new Error("config")
      }
    } catch {
      setErrorMessage("Server config JSON must decode to an object.")
      return
    }

    setServerSaving(true)
    setErrorMessage(null)
    try {
      const payload = {
        name: serverNameValue.trim(),
        transport: transportValue,
        config: parsedConfig,
        owner_scope_type: ownerScopeType,
        enabled: enabledValue
      }
      if (editingServerId) {
        await updateExternalServer(editingServerId, payload)
      } else {
        await createExternalServer({
          server_id: serverIdValue.trim(),
          ...payload
        })
      }
      resetServerForm()
      await loadServers()
    } catch {
      setErrorMessage(editingServerId ? "Failed to update external server." : "Failed to create external server.")
    } finally {
      setServerSaving(false)
    }
  }

  const handleDeleteServer = async (serverId: string) => {
    if (typeof window !== "undefined" && !window.confirm("Delete this external server?")) {
      return
    }
    setErrorMessage(null)
    try {
      await deleteExternalServer(serverId)
      await loadServers()
    } catch {
      setErrorMessage("Failed to delete external server.")
    }
  }

  return (
    <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
      <Typography.Text type="secondary">
        Managed external MCP servers are executable here. Legacy file or environment servers remain
        visible as read-only inventory until they are imported into MCP Hub.
      </Typography.Text>
      {errorMessage ? <Alert type="error" title={errorMessage} showIcon /> : null}

      <Button type="primary" onClick={openCreateForm}>
        New Managed Server
      </Button>

      {serverFormOpen ? (
        <Card title={editingServerId ? "Edit Managed Server" : "Create Managed Server"}>
          <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
            {!editingServerId ? (
              <Space orientation="vertical" style={{ width: "100%" }}>
                <label htmlFor="mcp-external-server-id">Server ID</label>
                <input
                  id="mcp-external-server-id"
                  aria-label="Server ID"
                  value={serverIdValue}
                  onChange={(event) => setServerIdValue(event.target.value)}
                  placeholder="docs-managed"
                />
              </Space>
            ) : null}

            <Space orientation="vertical" style={{ width: "100%" }}>
              <label htmlFor="mcp-external-server-name">Name</label>
              <input
                id="mcp-external-server-name"
                aria-label="Name"
                value={serverNameValue}
                onChange={(event) => setServerNameValue(event.target.value)}
                placeholder="Docs Managed"
              />
            </Space>

            <Space>
              <Space orientation="vertical">
                <label htmlFor="mcp-external-server-transport">Transport</label>
                <select
                  id="mcp-external-server-transport"
                  aria-label="Transport"
                  value={transportValue}
                  onChange={(event) => setTransportValue(event.target.value)}
                >
                  <option value="stdio">stdio</option>
                  <option value="websocket">websocket</option>
                </select>
              </Space>
              <Space orientation="vertical">
                <label htmlFor="mcp-external-server-scope">Owner Scope</label>
                <select
                  id="mcp-external-server-scope"
                  aria-label="Owner Scope"
                  value={ownerScopeType}
                  onChange={(event) =>
                    setOwnerScopeType(event.target.value as typeof ownerScopeType)
                  }
                >
                  <option value="global">Global</option>
                  <option value="org">Org</option>
                  <option value="team">Team</option>
                  <option value="user">User</option>
                </select>
              </Space>
            </Space>

            <Space orientation="vertical" style={{ width: "100%" }}>
              <label htmlFor="mcp-external-server-config">Config JSON</label>
              <textarea
                id="mcp-external-server-config"
                aria-label="Config JSON"
                value={configText}
                onChange={(event) => setConfigText(event.target.value)}
                rows={6}
              />
            </Space>

            <Checkbox checked={enabledValue} onChange={(event) => setEnabledValue(event.target.checked)}>
              Enabled
            </Checkbox>

            <Space>
              <Button type="primary" onClick={handleSaveServer} loading={serverSaving}>
                {editingServerId ? "Update Server" : "Save Server"}
              </Button>
              <Button onClick={resetServerForm}>Cancel</Button>
            </Space>
          </Space>
        </Card>
      ) : null}

      {managedServers.length > 0 ? (
        <Space>
          <label htmlFor="mcp-external-server">Server</label>
          <select
            id="mcp-external-server"
            aria-label="Server"
            value={activeServerId}
            onChange={(event) => setActiveServerId(event.target.value)}
          >
            {managedServers.map((server) => (
              <option key={server.id} value={server.id}>
                {server.name}
              </option>
            ))}
          </select>
        </Space>
      ) : (
        <Alert
          type="info"
          showIcon
          title="No managed external servers are available yet."
          description="Import a legacy server into MCP Hub before configuring secrets or bindings."
        />
      )}

      <Space orientation="vertical" style={{ width: "100%" }}>
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
            <Space wrap size="small" style={{ width: "100%", justifyContent: "space-between" }}>
              <Space wrap size="small">
                <Typography.Text strong>{server.name}</Typography.Text>
                {server.server_source === "legacy" ? (
                  <Tag>legacy read only</Tag>
                ) : (
                  <Tag color="green">managed</Tag>
                )}
                {server.secret_configured ? <Tag color="green">secret configured</Tag> : <Tag>no secret</Tag>}
                {server.runtime_executable ? <Tag color="green">runtime executable</Tag> : <Tag>inventory only</Tag>}
                <Tag>{`${server.binding_count || 0} ${(server.binding_count || 0) === 1 ? "binding" : "bindings"}`}</Tag>
                {server.superseded_by_server_id ? (
                  <Tag color="blue">{`superseded by ${server.superseded_by_server_id}`}</Tag>
                ) : null}
              </Space>
              {server.server_source === "legacy" && !server.superseded_by_server_id ? (
                <Button
                  size="small"
                  onClick={() => void handleImport(server.id)}
                  loading={importingServerId === server.id}
                >
                  Import to MCP Hub
                </Button>
              ) : server.server_source !== "legacy" ? (
                <Space>
                  <Button
                    size="small"
                    aria-label={`Edit ${server.name}`}
                    onClick={() => openEditForm(server)}
                  >
                    Edit
                  </Button>
                  <Button
                    size="small"
                    danger
                    aria-label={`Delete ${server.name}`}
                    onClick={() => void handleDeleteServer(server.id)}
                  >
                    Delete
                  </Button>
                </Space>
              ) : null}
            </Space>
          </List.Item>
        )}
      />
    </Space>
  )
}
