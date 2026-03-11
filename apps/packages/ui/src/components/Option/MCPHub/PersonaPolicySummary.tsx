import { useEffect, useState } from "react"
import { Alert, Button, Card, Empty, Space, Tag, Typography } from "antd"

import {
  getAssignmentExternalAccess,
  getEffectivePolicy,
  listPolicyAssignments,
  type McpHubEffectiveExternalAccess,
  type McpHubEffectivePolicy
} from "@/services/tldw/mcp-hub"

import { getPathAllowlistSummary, getPathScopeLabel } from "./policyHelpers"
import { ExternalAccessSummary } from "./ExternalAccessSummary"

type PersonaPolicySummaryProps = {
  personaId?: string | null
}

export const PersonaPolicySummary = ({ personaId }: PersonaPolicySummaryProps) => {
  const [policy, setPolicy] = useState<McpHubEffectivePolicy | null>(null)
  const [externalAccess, setExternalAccess] = useState<McpHubEffectiveExternalAccess | null>(null)
  const [loading, setLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      if (!personaId) {
        setPolicy(null)
        setExternalAccess(null)
        return
      }
      setLoading(true)
      setErrorMessage(null)
      try {
        const [next, assignmentRows] = await Promise.all([
          getEffectivePolicy({ persona_id: personaId }),
          listPolicyAssignments({ target_type: "persona", target_id: personaId })
        ])
        if (!cancelled) {
          setPolicy(next)
          const activeAssignment = (assignmentRows || []).find((row) => row.is_active)
          if (activeAssignment) {
            try {
              const summary = await getAssignmentExternalAccess(activeAssignment.id)
              if (!cancelled) {
                setExternalAccess(summary)
              }
            } catch {
              if (!cancelled) {
                setExternalAccess(null)
              }
            }
          } else {
            setExternalAccess(null)
          }
        }
      } catch {
        if (!cancelled) {
          setPolicy(null)
          setExternalAccess(null)
          setErrorMessage("Failed to load effective tool policy.")
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [personaId])

  return (
    <Card
      title="Tool Policy Summary"
      extra={
        <Button size="small" type="link" href="/settings/mcp-hub">
          Open MCP Hub
        </Button>
      }
    >
      {errorMessage ? <Alert type="error" title={errorMessage} showIcon /> : null}
      {!personaId ? (
        <Empty description="Select a persona to review its tool access." />
      ) : loading ? (
        <Typography.Text type="secondary">Loading effective policy...</Typography.Text>
      ) : policy ? (
        <Space orientation="vertical" size="small" style={{ width: "100%" }}>
          {getPathScopeLabel(policy.policy_document?.path_scope_mode) ? (
            <Typography.Text type="secondary">
              {`Local file scope: ${getPathScopeLabel(policy.policy_document?.path_scope_mode)}`}
            </Typography.Text>
          ) : null}
          {getPathAllowlistSummary(policy.policy_document?.path_allowlist_prefixes) ? (
            <Typography.Text type="secondary">
              {`Allowed paths: ${getPathAllowlistSummary(policy.policy_document?.path_allowlist_prefixes)}`}
            </Typography.Text>
          ) : null}
          {policy.selected_assignment_workspace_ids?.length ? (
            <Typography.Text type="secondary">
              {`Allowed workspaces: ${policy.selected_assignment_workspace_ids.join(", ")}`}
            </Typography.Text>
          ) : null}
          <Space wrap>
            {policy.capabilities.map((capability) => (
              <Tag key={capability}>{capability}</Tag>
            ))}
            {policy.approval_mode ? <Tag color="gold">{policy.approval_mode}</Tag> : null}
            {getPathScopeLabel(policy.policy_document?.path_scope_mode) ? (
              <Tag color="cyan">{getPathScopeLabel(policy.policy_document?.path_scope_mode)}</Tag>
            ) : null}
            {policy.policy_document?.path_scope_enforcement ? (
              <Tag color="orange">Path approval fallback</Tag>
            ) : null}
            {getPathAllowlistSummary(policy.policy_document?.path_allowlist_prefixes) ? (
              <Tag color="blue">{`paths ${getPathAllowlistSummary(policy.policy_document?.path_allowlist_prefixes)}`}</Tag>
            ) : null}
            {policy.provenance.some((entry) => entry.source_kind === "assignment_override") ? (
              <Tag color="cyan">Override active</Tag>
            ) : null}
            {policy.provenance.some((entry) => entry.source_kind === "assignment_path_scope_object") ? (
              <Tag color="purple">Named path scope</Tag>
            ) : null}
          </Space>
          <Space wrap>
            {policy.allowed_tools.map((tool) => (
              <Tag key={tool} color="green">
                {tool}
              </Tag>
            ))}
            {policy.denied_tools.map((tool) => (
              <Tag key={tool} color="red">
                {tool}
              </Tag>
            ))}
          </Space>
          <Typography.Text strong>External Services</Typography.Text>
          <ExternalAccessSummary
            summary={externalAccess}
            emptyText="No external service access is configured for this persona."
          />
        </Space>
      ) : (
        <Empty description="No tool policy is active for this persona yet." />
      )}
    </Card>
  )
}
