import { useEffect, useMemo, useState } from "react"
import { Alert, Button, Card, Checkbox, Empty, List, Space, Tag, Typography } from "antd"

import {
  createPolicyAssignment,
  deletePolicyAssignment,
  getEffectivePolicy,
  listApprovalPolicies,
  listPermissionProfiles,
  listPolicyAssignments,
  updatePolicyAssignment,
  type McpHubApprovalPolicy,
  type McpHubEffectivePolicy,
  type McpHubPermissionProfile,
  type McpHubPolicyAssignment
} from "@/services/tldw/mcp-hub"

import {
  buildPolicyDocument,
  MCP_HUB_CAPABILITY_OPTIONS,
  MCP_HUB_SCOPE_OPTIONS,
  MCP_HUB_TARGET_OPTIONS
} from "./policyHelpers"

export const PolicyAssignmentsTab = () => {
  const [assignments, setAssignments] = useState<McpHubPolicyAssignment[]>([])
  const [profiles, setProfiles] = useState<McpHubPermissionProfile[]>([])
  const [approvalPolicies, setApprovalPolicies] = useState<McpHubApprovalPolicy[]>([])
  const [effectivePolicy, setEffectivePolicy] = useState<McpHubEffectivePolicy | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [targetType, setTargetType] = useState<"default" | "group" | "persona">("persona")
  const [targetId, setTargetId] = useState("")
  const [ownerScopeType, setOwnerScopeType] = useState<"global" | "org" | "team" | "user">("user")
  const [profileId, setProfileId] = useState<string>("")
  const [approvalPolicyId, setApprovalPolicyId] = useState<string>("")
  const [capabilities, setCapabilities] = useState<string[]>([])
  const [allowedToolsText, setAllowedToolsText] = useState("")
  const [deniedToolsText, setDeniedToolsText] = useState("")
  const [isActive, setIsActive] = useState(true)

  const canSave = useMemo(() => !saving && (targetType === "default" || targetId.trim().length > 0), [
    saving,
    targetId,
    targetType
  ])

  const loadAll = async () => {
    setLoading(true)
    setErrorMessage(null)
    try {
      const [assignmentRows, profileRows, approvalRows] = await Promise.all([
        listPolicyAssignments(),
        listPermissionProfiles(),
        listApprovalPolicies()
      ])
      setAssignments(Array.isArray(assignmentRows) ? assignmentRows : [])
      setProfiles(Array.isArray(profileRows) ? profileRows : [])
      setApprovalPolicies(Array.isArray(approvalRows) ? approvalRows : [])

      const firstPersonaAssignment = assignmentRows.find((row) => row.target_type === "persona" && row.target_id)
      const firstGroupAssignment = assignmentRows.find((row) => row.target_type === "group" && row.target_id)
      const preview = await getEffectivePolicy({
        persona_id: firstPersonaAssignment?.target_id ?? null,
        group_id: firstGroupAssignment?.target_id ?? null
      })
      setEffectivePolicy(preview)
    } catch {
      setAssignments([])
      setProfiles([])
      setApprovalPolicies([])
      setEffectivePolicy(null)
      setErrorMessage("Failed to load policy assignments.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadAll()
  }, [])

  const resetForm = () => {
    setCreateOpen(false)
    setEditingId(null)
    setTargetType("persona")
    setTargetId("")
    setOwnerScopeType("user")
    setProfileId("")
    setApprovalPolicyId("")
    setCapabilities([])
    setAllowedToolsText("")
    setDeniedToolsText("")
    setIsActive(true)
  }

  const openForEdit = (assignment: McpHubPolicyAssignment) => {
    setCreateOpen(true)
    setEditingId(assignment.id)
    setTargetType(assignment.target_type)
    setTargetId(String(assignment.target_id || ""))
    setOwnerScopeType(assignment.owner_scope_type)
    setProfileId(assignment.profile_id ? String(assignment.profile_id) : "")
    setApprovalPolicyId(assignment.approval_policy_id ? String(assignment.approval_policy_id) : "")
    setCapabilities(
      Array.isArray(assignment.inline_policy_document.capabilities)
        ? assignment.inline_policy_document.capabilities
        : []
    )
    setAllowedToolsText(
      Array.isArray(assignment.inline_policy_document.allowed_tools)
        ? assignment.inline_policy_document.allowed_tools.join("\n")
        : ""
    )
    setDeniedToolsText(
      Array.isArray(assignment.inline_policy_document.denied_tools)
        ? assignment.inline_policy_document.denied_tools.join("\n")
        : ""
    )
    setIsActive(assignment.is_active)
  }

  const handleSave = async () => {
    if (!canSave) return
    setSaving(true)
    setErrorMessage(null)
    try {
      const payload = {
        target_type: targetType,
        target_id: targetType === "default" ? null : targetId.trim(),
        owner_scope_type: ownerScopeType,
        profile_id: profileId ? Number(profileId) : null,
        approval_policy_id: approvalPolicyId ? Number(approvalPolicyId) : null,
        inline_policy_document: buildPolicyDocument({
          capabilities,
          allowedToolsText,
          deniedToolsText
        }),
        is_active: isActive
      }
      if (editingId) {
        await updatePolicyAssignment(editingId, payload)
      } else {
        await createPolicyAssignment(payload)
      }
      resetForm()
      await loadAll()
    } catch {
      setErrorMessage(
        editingId ? "Failed to update policy assignment." : "Failed to create policy assignment."
      )
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (assignmentId: number) => {
    if (typeof window !== "undefined" && !window.confirm("Delete this policy assignment?")) {
      return
    }
    setErrorMessage(null)
    try {
      await deletePolicyAssignment(assignmentId)
      await loadAll()
    } catch {
      setErrorMessage("Failed to delete policy assignment.")
    }
  }

  return (
    <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
      <Typography.Text type="secondary">
        Assign profiles to default, group, or persona targets, then layer in manual overrides where needed.
      </Typography.Text>
      {errorMessage ? <Alert type="error" title={errorMessage} showIcon /> : null}

      <Button type="primary" onClick={() => setCreateOpen(true)}>
        New Assignment
      </Button>

      {createOpen ? (
        <Card title={editingId ? "Edit Policy Assignment" : "Create Policy Assignment"}>
          <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
            <Space>
              <Space orientation="vertical">
                <label htmlFor="mcp-assignment-target-type">Target Type</label>
                <select
                  id="mcp-assignment-target-type"
                  aria-label="Target Type"
                  value={targetType}
                  onChange={(event) => setTargetType(event.target.value as typeof targetType)}
                >
                  {MCP_HUB_TARGET_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </Space>
              <Space orientation="vertical">
                <label htmlFor="mcp-assignment-scope">Owner Scope</label>
                <select
                  id="mcp-assignment-scope"
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
            </Space>
            {targetType !== "default" ? (
              <Space orientation="vertical" style={{ width: "100%" }}>
                <label htmlFor="mcp-assignment-target-id">Target Id</label>
                <input
                  id="mcp-assignment-target-id"
                  aria-label="Target Id"
                  value={targetId}
                  onChange={(event) => setTargetId(event.target.value)}
                  placeholder={targetType === "persona" ? "researcher" : "team-red"}
                />
              </Space>
            ) : null}
            <Space>
              <Space orientation="vertical">
                <label htmlFor="mcp-assignment-profile">Referenced Profile</label>
                <select
                  id="mcp-assignment-profile"
                  aria-label="Referenced Profile"
                  value={profileId}
                  onChange={(event) => setProfileId(event.target.value)}
                >
                  <option value="">Manual only</option>
                  {profiles.map((profile) => (
                    <option key={profile.id} value={profile.id}>
                      {profile.name}
                    </option>
                  ))}
                </select>
              </Space>
              <Space orientation="vertical">
                <label htmlFor="mcp-assignment-approval-policy">Approval Policy</label>
                <select
                  id="mcp-assignment-approval-policy"
                  aria-label="Approval Policy"
                  value={approvalPolicyId}
                  onChange={(event) => setApprovalPolicyId(event.target.value)}
                >
                  <option value="">No runtime approval</option>
                  {approvalPolicies.map((policy) => (
                    <option key={policy.id} value={policy.id}>
                      {policy.name}
                    </option>
                  ))}
                </select>
              </Space>
            </Space>
            <Space orientation="vertical" style={{ width: "100%" }}>
              <Typography.Text strong>Inline Capabilities</Typography.Text>
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
              <label htmlFor="mcp-assignment-allowed-tools">Allowed Tools</label>
              <textarea
                id="mcp-assignment-allowed-tools"
                aria-label="Allowed Tools"
                value={allowedToolsText}
                onChange={(event) => setAllowedToolsText(event.target.value)}
                rows={3}
              />
            </Space>
            <Space orientation="vertical" style={{ width: "100%" }}>
              <label htmlFor="mcp-assignment-denied-tools">Denied Tools</label>
              <textarea
                id="mcp-assignment-denied-tools"
                aria-label="Denied Tools"
                value={deniedToolsText}
                onChange={(event) => setDeniedToolsText(event.target.value)}
                rows={3}
              />
            </Space>
            <Checkbox checked={isActive} onChange={(event) => setIsActive(event.target.checked)}>
              Active
            </Checkbox>
            <Space>
              <Button type="primary" onClick={handleSave} disabled={!canSave} loading={saving}>
                {editingId ? "Update Assignment" : "Save Assignment"}
              </Button>
              <Button onClick={resetForm}>Cancel</Button>
            </Space>
          </Space>
        </Card>
      ) : null}

      <Card title="Current Effective Preview">
        {effectivePolicy ? (
          <Space orientation="vertical" size="small" style={{ width: "100%" }}>
            <Space wrap>
              {effectivePolicy.capabilities.map((capability) => (
                <Tag key={capability}>{capability}</Tag>
              ))}
              {effectivePolicy.allowed_tools.map((tool) => (
                <Tag key={tool} color="green">
                  {tool}
                </Tag>
              ))}
              {effectivePolicy.denied_tools.map((tool) => (
                <Tag key={tool} color="red">
                  {tool}
                </Tag>
              ))}
              {effectivePolicy.approval_mode ? (
                <Tag color="gold">{effectivePolicy.approval_mode}</Tag>
              ) : null}
            </Space>
          </Space>
        ) : (
          <Empty description="No effective policy preview available yet" />
        )}
      </Card>

      <List
        bordered
        loading={loading}
        dataSource={assignments}
        locale={{ emptyText: <Empty description="No assignments yet" /> }}
        renderItem={(assignment) => (
          <List.Item>
            <Space orientation="vertical" size={4} style={{ width: "100%" }}>
              <Space wrap>
                <Typography.Text strong>{assignment.target_id || assignment.target_type}</Typography.Text>
                <Tag>{assignment.target_type}</Tag>
                <Tag>{assignment.owner_scope_type}</Tag>
                {assignment.profile_id ? <Tag color="blue">{`profile ${assignment.profile_id}`}</Tag> : null}
                {assignment.approval_policy_id ? (
                  <Tag color="gold">{`approval ${assignment.approval_policy_id}`}</Tag>
                ) : null}
                {assignment.is_active ? <Tag color="green">active</Tag> : <Tag>inactive</Tag>}
                <Button size="small" onClick={() => openForEdit(assignment)}>
                  Edit
                </Button>
                <Button size="small" danger onClick={() => void handleDelete(assignment.id)}>
                  Delete
                </Button>
              </Space>
              <Space wrap>
                {(assignment.inline_policy_document.capabilities || []).map((capability) => (
                  <Tag key={capability}>{capability}</Tag>
                ))}
              </Space>
            </Space>
          </List.Item>
        )}
      />
    </Space>
  )
}
