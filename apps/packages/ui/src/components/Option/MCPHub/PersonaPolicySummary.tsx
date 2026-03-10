import { useEffect, useState } from "react"
import { Alert, Button, Card, Empty, Space, Tag, Typography } from "antd"

import { getEffectivePolicy, type McpHubEffectivePolicy } from "@/services/tldw/mcp-hub"

import { getPathScopeLabel } from "./policyHelpers"

type PersonaPolicySummaryProps = {
  personaId?: string | null
}

export const PersonaPolicySummary = ({ personaId }: PersonaPolicySummaryProps) => {
  const [policy, setPolicy] = useState<McpHubEffectivePolicy | null>(null)
  const [loading, setLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      if (!personaId) {
        setPolicy(null)
        return
      }
      setLoading(true)
      setErrorMessage(null)
      try {
        const next = await getEffectivePolicy({ persona_id: personaId })
        if (!cancelled) {
          setPolicy(next)
        }
      } catch {
        if (!cancelled) {
          setPolicy(null)
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
            {policy.provenance.some((entry) => entry.source_kind === "assignment_override") ? (
              <Tag color="cyan">Override active</Tag>
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
        </Space>
      ) : (
        <Empty description="No tool policy is active for this persona yet." />
      )}
    </Card>
  )
}
