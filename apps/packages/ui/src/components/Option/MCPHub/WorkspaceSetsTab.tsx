import { useEffect, useState } from "react"
import { Alert, Button, Card, Empty, List, Space, Tag, Typography } from "antd"

import {
  addWorkspaceSetMember,
  createWorkspaceSetObject,
  deleteWorkspaceSetMember,
  deleteWorkspaceSetObject,
  listWorkspaceSetMembers,
  listWorkspaceSetObjects,
  updateWorkspaceSetObject,
  type McpHubWorkspaceSetObject,
  type McpHubWorkspaceSetObjectMember
} from "@/services/tldw/mcp-hub"

import { parseLineList } from "./policyHelpers"

export const WorkspaceSetsTab = () => {
  const [objects, setObjects] = useState<McpHubWorkspaceSetObject[]>([])
  const [membersByObjectId, setMembersByObjectId] = useState<Record<number, McpHubWorkspaceSetObjectMember[]>>({})
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [workspaceIdsText, setWorkspaceIdsText] = useState("")
  const [isActive, setIsActive] = useState(true)

  const loadObjects = async () => {
    setLoading(true)
    setErrorMessage(null)
    try {
      const rows = await listWorkspaceSetObjects()
      const nextObjects = Array.isArray(rows) ? rows : []
      setObjects(nextObjects)
      const memberEntries = await Promise.all(
        nextObjects.map(async (workspaceSet) => [
          workspaceSet.id,
          await listWorkspaceSetMembers(workspaceSet.id)
        ] as const)
      )
      setMembersByObjectId(
        Object.fromEntries(
          memberEntries.map(([workspaceSetObjectId, members]) => [
            workspaceSetObjectId,
            Array.isArray(members) ? members : []
          ])
        )
      )
    } catch {
      setObjects([])
      setMembersByObjectId({})
      setErrorMessage("Failed to load workspace sets.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadObjects()
  }, [])

  const resetForm = () => {
    setCreateOpen(false)
    setEditingId(null)
    setName("")
    setDescription("")
    setWorkspaceIdsText("")
    setIsActive(true)
  }

  const openForEdit = (workspaceSet: McpHubWorkspaceSetObject) => {
    setCreateOpen(true)
    setEditingId(workspaceSet.id)
    setName(workspaceSet.name)
    setDescription(String(workspaceSet.description || ""))
    setWorkspaceIdsText(
      (membersByObjectId[workspaceSet.id] || []).map((member) => member.workspace_id).join("\n")
    )
    setIsActive(workspaceSet.is_active)
  }

  const syncMembers = async (workspaceSetObjectId: number) => {
    const desiredWorkspaceIds = Array.from(new Set(parseLineList(workspaceIdsText)))
    const currentWorkspaceIds = (membersByObjectId[workspaceSetObjectId] || []).map(
      (member) => member.workspace_id
    )
    const toAdd = desiredWorkspaceIds.filter((workspaceId) => !currentWorkspaceIds.includes(workspaceId))
    const toDelete = currentWorkspaceIds.filter((workspaceId) => !desiredWorkspaceIds.includes(workspaceId))

    await Promise.all([
      ...toAdd.map((workspaceId) => addWorkspaceSetMember(workspaceSetObjectId, workspaceId)),
      ...toDelete.map((workspaceId) => deleteWorkspaceSetMember(workspaceSetObjectId, workspaceId))
    ])
  }

  const handleSave = async () => {
    if (!name.trim() || saving) return
    setSaving(true)
    setErrorMessage(null)
    try {
      const payload = {
        name: name.trim(),
        description: description.trim() || null,
        owner_scope_type: "user" as const,
        is_active: isActive
      }
      let workspaceSetObjectId = editingId
      if (editingId) {
        const updated = await updateWorkspaceSetObject(editingId, payload)
        workspaceSetObjectId = updated.id
      } else {
        const created = await createWorkspaceSetObject(payload)
        workspaceSetObjectId = created.id
      }
      if (workspaceSetObjectId) {
        await syncMembers(workspaceSetObjectId)
      }
      resetForm()
      await loadObjects()
    } catch {
      setErrorMessage(editingId ? "Failed to update workspace set." : "Failed to create workspace set.")
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (workspaceSetObjectId: number) => {
    if (typeof window !== "undefined" && !window.confirm("Delete this workspace set?")) {
      return
    }
    setErrorMessage(null)
    try {
      await deleteWorkspaceSetObject(workspaceSetObjectId)
      await loadObjects()
    } catch {
      setErrorMessage("Failed to delete workspace set.")
    }
  }

  return (
    <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
      <Typography.Text type="secondary">
        Reusable workspace sets let assignments share the same trusted workspace membership without
        duplicating inline ids.
      </Typography.Text>
      {errorMessage ? <Alert type="error" title={errorMessage} showIcon /> : null}

      <Button type="primary" onClick={() => setCreateOpen(true)}>
        New Workspace Set
      </Button>

      {createOpen ? (
        <Card title={editingId ? "Edit Workspace Set" : "Create Workspace Set"}>
          <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
            <Space orientation="vertical" style={{ width: "100%" }}>
              <label htmlFor="mcp-workspace-set-name">Workspace Set Name</label>
              <input
                id="mcp-workspace-set-name"
                aria-label="Workspace Set Name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Primary Workspace Set"
              />
            </Space>
            <Space orientation="vertical" style={{ width: "100%" }}>
              <label htmlFor="mcp-workspace-set-description">Description</label>
              <input
                id="mcp-workspace-set-description"
                aria-label="Workspace Set Description"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="Reusable trusted workspace membership for research personas"
              />
            </Space>
            <Space orientation="vertical" style={{ width: "100%" }}>
              <label htmlFor="mcp-workspace-set-workspace-ids">Workspace ids</label>
              <textarea
                id="mcp-workspace-set-workspace-ids"
                aria-label="Workspace ids"
                value={workspaceIdsText}
                onChange={(event) => setWorkspaceIdsText(event.target.value)}
                rows={4}
              />
              <Typography.Text type="secondary">
                One trusted workspace id per line. Only server-known workspaces for the current user are
                accepted.
              </Typography.Text>
            </Space>
            <label>
              <input
                type="checkbox"
                checked={isActive}
                onChange={(event) => setIsActive(event.target.checked)}
              />
              <span style={{ marginLeft: 8 }}>Active</span>
            </label>
            <Space>
              <Button type="primary" onClick={() => void handleSave()} loading={saving}>
                {editingId ? "Update Workspace Set" : "Save Workspace Set"}
              </Button>
              <Button onClick={resetForm}>Cancel</Button>
            </Space>
          </Space>
        </Card>
      ) : null}

      <List
        bordered
        loading={loading}
        dataSource={objects}
        locale={{ emptyText: <Empty description="No workspace sets yet" /> }}
        renderItem={(workspaceSet) => (
          <List.Item>
            <Space orientation="vertical" size={4} style={{ width: "100%" }}>
              <Space wrap>
                <Typography.Text strong>{workspaceSet.name}</Typography.Text>
                <Tag>{workspaceSet.owner_scope_type}</Tag>
                {workspaceSet.is_active ? <Tag color="green">active</Tag> : <Tag>inactive</Tag>}
                <Button size="small" onClick={() => openForEdit(workspaceSet)}>
                  Edit
                </Button>
                <Button size="small" danger onClick={() => void handleDelete(workspaceSet.id)}>
                  Delete
                </Button>
              </Space>
              {workspaceSet.description ? (
                <Typography.Text type="secondary">{workspaceSet.description}</Typography.Text>
              ) : null}
              {(membersByObjectId[workspaceSet.id] || []).length > 0 ? (
                <Space wrap size={4}>
                  {(membersByObjectId[workspaceSet.id] || []).map((member) => (
                    <Tag key={`${workspaceSet.id}-${member.workspace_id}`} color="purple">
                      {member.workspace_id}
                    </Tag>
                  ))}
                </Space>
              ) : (
                <Typography.Text type="secondary">No workspace ids configured yet.</Typography.Text>
              )}
            </Space>
          </List.Item>
        )}
      />
    </Space>
  )
}
