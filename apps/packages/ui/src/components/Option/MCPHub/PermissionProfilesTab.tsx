import { useEffect, useMemo, useState } from "react"
import { Alert, Button, Card, Checkbox, Empty, List, Space, Tag, Typography } from "antd"

import {
  createPermissionProfile,
  deletePermissionProfile,
  listPermissionProfiles,
  updatePermissionProfile,
  type McpHubPermissionProfile
} from "@/services/tldw/mcp-hub"

import {
  buildPolicyDocument,
  MCP_HUB_CAPABILITY_OPTIONS,
  MCP_HUB_PROFILE_MODE_OPTIONS,
  MCP_HUB_SCOPE_OPTIONS
} from "./policyHelpers"

export const PermissionProfilesTab = () => {
  const [profiles, setProfiles] = useState<McpHubPermissionProfile[]>([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [ownerScopeType, setOwnerScopeType] = useState<"global" | "org" | "team" | "user">("global")
  const [mode, setMode] = useState<"custom" | "preset">("custom")
  const [capabilities, setCapabilities] = useState<string[]>([])
  const [allowedToolsText, setAllowedToolsText] = useState("")
  const [deniedToolsText, setDeniedToolsText] = useState("")
  const [isActive, setIsActive] = useState(true)

  const canSave = useMemo(() => name.trim().length > 0 && !saving, [name, saving])

  const loadProfiles = async () => {
    setLoading(true)
    setErrorMessage(null)
    try {
      const rows = await listPermissionProfiles()
      setProfiles(Array.isArray(rows) ? rows : [])
    } catch {
      setProfiles([])
      setErrorMessage("Failed to load MCP Hub permission profiles.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadProfiles()
  }, [])

  const resetForm = () => {
    setCreateOpen(false)
    setEditingId(null)
    setName("")
    setDescription("")
    setOwnerScopeType("global")
    setMode("custom")
    setCapabilities([])
    setAllowedToolsText("")
    setDeniedToolsText("")
    setIsActive(true)
  }

  const openForEdit = (profile: McpHubPermissionProfile) => {
    setCreateOpen(true)
    setEditingId(profile.id)
    setName(profile.name)
    setDescription(String(profile.description || ""))
    setOwnerScopeType(profile.owner_scope_type)
    setMode(profile.mode)
    setCapabilities(Array.isArray(profile.policy_document.capabilities) ? profile.policy_document.capabilities : [])
    setAllowedToolsText(Array.isArray(profile.policy_document.allowed_tools) ? profile.policy_document.allowed_tools.join("\n") : "")
    setDeniedToolsText(Array.isArray(profile.policy_document.denied_tools) ? profile.policy_document.denied_tools.join("\n") : "")
    setIsActive(profile.is_active)
  }

  const handleSave = async () => {
    if (!canSave) return
    setSaving(true)
    setErrorMessage(null)
    try {
      const payload = {
        name: name.trim(),
        description: description.trim() || null,
        owner_scope_type: ownerScopeType,
        mode,
        policy_document: buildPolicyDocument({
          capabilities,
          allowedToolsText,
          deniedToolsText
        }),
        is_active: isActive
      }
      if (editingId) {
        await updatePermissionProfile(editingId, payload)
      } else {
        await createPermissionProfile(payload)
      }
      resetForm()
      await loadProfiles()
    } catch {
      setErrorMessage(
        editingId
          ? "Failed to update MCP Hub permission profile."
          : "Failed to create MCP Hub permission profile."
      )
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (profileId: number) => {
    if (typeof window !== "undefined" && !window.confirm("Delete this permission profile?")) {
      return
    }
    setErrorMessage(null)
    try {
      await deletePermissionProfile(profileId)
      await loadProfiles()
    } catch {
      setErrorMessage("Failed to delete MCP Hub permission profile.")
    }
  }

  return (
    <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
      <Typography.Text type="secondary">
        Reusable tool-access profiles define capabilities, tool allowlists, and baseline restrictions.
      </Typography.Text>
      {errorMessage ? <Alert type="error" title={errorMessage} showIcon /> : null}

      <Button type="primary" onClick={() => setCreateOpen(true)}>
        New Profile
      </Button>

      {createOpen ? (
        <Card title={editingId ? "Edit Permission Profile" : "Create Permission Profile"}>
          <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
            <Space orientation="vertical" style={{ width: "100%" }}>
              <label htmlFor="mcp-permission-profile-name">Profile Name</label>
              <input
                id="mcp-permission-profile-name"
                aria-label="Profile Name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Process Exec"
              />
            </Space>
            <Space orientation="vertical" style={{ width: "100%" }}>
              <label htmlFor="mcp-permission-profile-description">Description</label>
              <input
                id="mcp-permission-profile-description"
                aria-label="Description"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="Allows tool execution for shell workflows"
              />
            </Space>
            <Space>
              <Space orientation="vertical">
                <label htmlFor="mcp-permission-profile-scope">Owner Scope</label>
                <select
                  id="mcp-permission-profile-scope"
                  aria-label="Owner Scope"
                  value={ownerScopeType}
                  onChange={(event) => setOwnerScopeType(event.target.value as typeof ownerScopeType)}
                >
                  {MCP_HUB_SCOPE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </Space>
              <Space orientation="vertical">
                <label htmlFor="mcp-permission-profile-mode">Profile Mode</label>
                <select
                  id="mcp-permission-profile-mode"
                  aria-label="Profile Mode"
                  value={mode}
                  onChange={(event) => setMode(event.target.value as typeof mode)}
                >
                  {MCP_HUB_PROFILE_MODE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </Space>
            </Space>
            <Space orientation="vertical" style={{ width: "100%" }}>
              <Typography.Text strong>Capabilities</Typography.Text>
              <Space wrap>
                {MCP_HUB_CAPABILITY_OPTIONS.map((capability) => (
                  <Checkbox
                    key={capability}
                    checked={capabilities.includes(capability)}
                    onChange={(event) => {
                      setCapabilities((prev) =>
                        event.target.checked
                          ? [...prev, capability]
                          : prev.filter((entry) => entry !== capability)
                      )
                    }}
                  >
                    {capability}
                  </Checkbox>
                ))}
              </Space>
            </Space>
            <Space orientation="vertical" style={{ width: "100%" }}>
              <label htmlFor="mcp-permission-profile-allowed-tools">Allowed Tools</label>
              <textarea
                id="mcp-permission-profile-allowed-tools"
                aria-label="Allowed Tools"
                value={allowedToolsText}
                onChange={(event) => setAllowedToolsText(event.target.value)}
                placeholder={"Bash(git *)\nnotes.search"}
                rows={4}
              />
            </Space>
            <Space orientation="vertical" style={{ width: "100%" }}>
              <label htmlFor="mcp-permission-profile-denied-tools">Denied Tools</label>
              <textarea
                id="mcp-permission-profile-denied-tools"
                aria-label="Denied Tools"
                value={deniedToolsText}
                onChange={(event) => setDeniedToolsText(event.target.value)}
                placeholder={"Bash(rm *)\nBash(sudo *)"}
                rows={4}
              />
            </Space>
            <Checkbox checked={isActive} onChange={(event) => setIsActive(event.target.checked)}>
              Active
            </Checkbox>
            <Space>
              <Button type="primary" onClick={handleSave} disabled={!canSave} loading={saving}>
                {editingId ? "Update Profile" : "Save Profile"}
              </Button>
              <Button onClick={resetForm}>Cancel</Button>
            </Space>
          </Space>
        </Card>
      ) : null}

      <List
        bordered
        loading={loading}
        dataSource={profiles}
        locale={{ emptyText: <Empty description="No permission profiles yet" /> }}
        renderItem={(profile) => (
          <List.Item>
            <Space orientation="vertical" size={4} style={{ width: "100%" }}>
              <Space wrap>
                <Typography.Text strong>{profile.name}</Typography.Text>
                <Tag>{profile.owner_scope_type}</Tag>
                <Tag color="blue">{profile.mode}</Tag>
                {profile.is_active ? <Tag color="green">active</Tag> : <Tag>inactive</Tag>}
                <Button size="small" onClick={() => openForEdit(profile)}>
                  Edit
                </Button>
                <Button size="small" danger onClick={() => void handleDelete(profile.id)}>
                  Delete
                </Button>
              </Space>
              {profile.description ? (
                <Typography.Text type="secondary">{profile.description}</Typography.Text>
              ) : null}
              <Space wrap>
                {(profile.policy_document.capabilities || []).map((capability) => (
                  <Tag key={capability}>{capability}</Tag>
                ))}
                {(profile.policy_document.allowed_tools || []).map((tool) => (
                  <Tag key={tool} color="green">
                    {tool}
                  </Tag>
                ))}
                {(profile.policy_document.denied_tools || []).map((tool) => (
                  <Tag key={tool} color="red">
                    {tool}
                  </Tag>
                ))}
              </Space>
            </Space>
          </List.Item>
        )}
      />
    </Space>
  )
}
