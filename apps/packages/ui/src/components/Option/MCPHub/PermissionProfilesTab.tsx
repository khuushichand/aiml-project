import { useEffect, useMemo, useState } from "react"
import { Alert, Button, Card, Checkbox, Empty, List, Space, Tag, Typography } from "antd"

import {
  createPermissionProfile,
  deletePermissionProfile,
  getToolRegistrySummary,
  listExternalServers,
  listProfileCredentialBindings,
  listPermissionProfiles,
  deleteProfileCredentialBinding,
  upsertProfileCredentialBinding,
  updatePermissionProfile,
  type McpHubCredentialBinding,
  type McpHubExternalServer,
  type McpHubPermissionPolicyDocument,
  type McpHubPermissionProfile,
  type McpHubToolRegistryEntry,
  type McpHubToolRegistryModule
} from "@/services/tldw/mcp-hub"

import {
  getCredentialBindingKey,
  getManagedExternalServers,
  getManagedExternalServerSlots,
  MCP_HUB_PROFILE_MODE_OPTIONS,
  MCP_HUB_SCOPE_OPTIONS
} from "./policyHelpers"
import { PolicyDocumentEditor } from "./PolicyDocumentEditor"

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
  const [policyDocument, setPolicyDocument] = useState<McpHubPermissionPolicyDocument>({})
  const [isActive, setIsActive] = useState(true)
  const [registryEntries, setRegistryEntries] = useState<McpHubToolRegistryEntry[]>([])
  const [registryModules, setRegistryModules] = useState<McpHubToolRegistryModule[]>([])
  const [externalServers, setExternalServers] = useState<McpHubExternalServer[]>([])
  const [profileBindings, setProfileBindings] = useState<McpHubCredentialBinding[]>([])
  const [bindingsLoading, setBindingsLoading] = useState(false)
  const [bindingServerId, setBindingServerId] = useState<string | null>(null)
  const managedExternalServers = useMemo(
    () => getManagedExternalServers(externalServers),
    [externalServers]
  )
  const grantedBindingKeys = useMemo(
    () =>
      new Set(
        profileBindings.map((binding) =>
          getCredentialBindingKey(binding.external_server_id, binding.slot_name)
        )
      ),
    [profileBindings]
  )

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

  useEffect(() => {
    let cancelled = false
    const loadRegistryAndServers = async () => {
      try {
        const [summary, serverRows] = await Promise.all([
          getToolRegistrySummary(),
          listExternalServers()
        ])
        if (!cancelled) {
          setRegistryEntries(Array.isArray(summary?.entries) ? summary.entries : [])
          setRegistryModules(Array.isArray(summary?.modules) ? summary.modules : [])
          setExternalServers(Array.isArray(serverRows) ? serverRows : [])
        }
      } catch {
        if (!cancelled) {
          setRegistryEntries([])
          setRegistryModules([])
          setExternalServers([])
        }
      }
    }
    void loadRegistryAndServers()
    return () => {
      cancelled = true
    }
  }, [])

  const resetForm = () => {
    setCreateOpen(false)
    setEditingId(null)
    setName("")
    setDescription("")
    setOwnerScopeType("global")
    setMode("custom")
    setPolicyDocument({})
    setIsActive(true)
    setProfileBindings([])
    setBindingsLoading(false)
    setBindingServerId(null)
  }

  const loadProfileBindings = async (profileId: number) => {
    setBindingsLoading(true)
    try {
      const rows = await listProfileCredentialBindings(profileId)
      setProfileBindings(Array.isArray(rows) ? rows : [])
    } catch {
      setProfileBindings([])
      setErrorMessage("Failed to load external server bindings.")
    } finally {
      setBindingsLoading(false)
    }
  }

  const openForEdit = (profile: McpHubPermissionProfile) => {
    setCreateOpen(true)
    setEditingId(profile.id)
    setName(profile.name)
    setDescription(String(profile.description || ""))
    setOwnerScopeType(profile.owner_scope_type)
    setMode(profile.mode)
    setPolicyDocument(profile.policy_document || {})
    setIsActive(profile.is_active)
    setProfileBindings([])
    void loadProfileBindings(profile.id)
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
        policy_document: policyDocument,
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

  const handleToggleExternalServer = async (
    serverId: string,
    checked: boolean,
    slotName?: string | null
  ) => {
    if (!editingId) return
    setBindingServerId(getCredentialBindingKey(serverId, slotName))
    setErrorMessage(null)
    try {
      if (checked) {
        await upsertProfileCredentialBinding(editingId, serverId, slotName)
      } else {
        await deleteProfileCredentialBinding(editingId, serverId, slotName)
      }
      const [bindingRows, serverRows] = await Promise.all([
        listProfileCredentialBindings(editingId),
        listExternalServers()
      ])
      setProfileBindings(Array.isArray(bindingRows) ? bindingRows : [])
      setExternalServers(Array.isArray(serverRows) ? serverRows : [])
    } catch {
      setErrorMessage("Failed to update external server binding.")
    } finally {
      setBindingServerId(null)
    }
  }

  return (
    <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
      <Typography.Text type="secondary">
        Reusable tool-access profiles define capabilities, exact tool allowlists, and baseline restrictions.
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
                placeholder="Read Only"
              />
            </Space>
            <Space orientation="vertical" style={{ width: "100%" }}>
              <label htmlFor="mcp-permission-profile-description">Description</label>
              <input
                id="mcp-permission-profile-description"
                aria-label="Description"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="Restricts this persona to low-risk read flows"
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

            <PolicyDocumentEditor
              formId="mcp-permission-profile"
              policy={policyDocument}
              onChange={setPolicyDocument}
              registryEntries={registryEntries}
              registryModules={registryModules}
            />

            {editingId ? (
              <Card size="small" title="External Service Bindings">
                <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
                  <Typography.Text type="secondary">
                    Grant reusable access to managed external MCP servers here. Legacy inventory is
                    visible in External Servers and cannot be selected until imported into MCP Hub.
                  </Typography.Text>
                  {bindingsLoading ? (
                    <Typography.Text type="secondary">Loading external service bindings...</Typography.Text>
                  ) : managedExternalServers.length > 0 ? (
                    <Space orientation="vertical" size="small" style={{ width: "100%" }}>
                      {managedExternalServers.map((server) => {
                        const slots = getManagedExternalServerSlots(server)
                        return (
                          <Card key={server.id} size="small" title={server.name}>
                            <Space orientation="vertical" size="small" style={{ width: "100%" }}>
                              <Space wrap size={4}>
                                {server.secret_configured ? (
                                  <Tag color="green">secret configured</Tag>
                                ) : (
                                  <Tag>no secret</Tag>
                                )}
                                {server.binding_count ? (
                                  <Tag>{`${server.binding_count} bindings`}</Tag>
                                ) : null}
                              </Space>
                              {slots.length > 0 ? (
                                <Space orientation="vertical" size="small" style={{ width: "100%" }}>
                                  {slots.map((slot) => {
                                    const bindingKey = getCredentialBindingKey(server.id, slot.slot_name)
                                    return (
                                      <Checkbox
                                        key={bindingKey}
                                        checked={grantedBindingKeys.has(bindingKey)}
                                        disabled={bindingServerId === bindingKey}
                                        onChange={(event) =>
                                          void handleToggleExternalServer(
                                            server.id,
                                            event.target.checked,
                                            slot.slot_name
                                          )
                                        }
                                      >
                                        <Space wrap size={4}>
                                          <span>{slot.display_name}</span>
                                          <Tag>{slot.slot_name}</Tag>
                                          <Tag>{slot.privilege_class}</Tag>
                                          {slot.secret_configured ? (
                                            <Tag color="green">slot secret configured</Tag>
                                          ) : (
                                            <Tag>slot secret missing</Tag>
                                          )}
                                        </Space>
                                      </Checkbox>
                                    )
                                  })}
                                </Space>
                              ) : (
                                <Typography.Text type="secondary">
                                  Define credential slots in External Servers before binding this service.
                                </Typography.Text>
                              )}
                            </Space>
                          </Card>
                        )
                      })}
                    </Space>
                  ) : (
                    <Empty description="No managed external servers are available yet." />
                  )}
                </Space>
              </Card>
            ) : null}

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
