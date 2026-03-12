import { useEffect, useState } from "react"
import { Alert, Button, Card, Empty, List, Space, Tag, Typography } from "antd"

import {
  listGovernanceAuditFindings,
  type McpHubGovernanceAuditFinding,
  type McpHubGovernanceAuditFindingType,
  type McpHubGovernanceAuditNavigateTarget
} from "@/services/tldw/mcp-hub"

type GovernanceAuditTabProps = {
  onOpen?: (target: McpHubGovernanceAuditNavigateTarget) => void
}

const severityColor = (severity: "error" | "warning"): "red" | "gold" =>
  severity === "error" ? "red" : "gold"

export const GovernanceAuditTab = ({ onOpen }: GovernanceAuditTabProps) => {
  const [items, setItems] = useState<McpHubGovernanceAuditFinding[]>([])
  const [loading, setLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [counts, setCounts] = useState({ error: 0, warning: 0 })
  const [severityFilter, setSeverityFilter] = useState<"all" | "error" | "warning">("all")
  const [findingTypeFilter, setFindingTypeFilter] = useState<"all" | McpHubGovernanceAuditFindingType>("all")

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      setLoading(true)
      setErrorMessage(null)
      try {
        const result = await listGovernanceAuditFindings({
          severity: severityFilter === "all" ? undefined : severityFilter,
          finding_type: findingTypeFilter === "all" ? undefined : findingTypeFilter
        })
        if (!cancelled) {
          setItems(Array.isArray(result?.items) ? result.items : [])
          setCounts({
            error: Number(result?.counts?.error || 0),
            warning: Number(result?.counts?.warning || 0)
          })
        }
      } catch {
        if (!cancelled) {
          setItems([])
          setCounts({ error: 0, warning: 0 })
          setErrorMessage("Failed to load governance audit findings.")
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
  }, [findingTypeFilter, severityFilter])

  return (
    <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
      <Typography.Text type="secondary">
        Audit aggregates concrete governance findings across the visible MCP Hub configuration.
        Multi-root readiness findings are advisory; assignment blockers remain the enforcement
        boundary.
      </Typography.Text>
      {errorMessage ? <Alert type="error" title={errorMessage} showIcon /> : null}

      <Card>
        <Space wrap align="start">
          <Tag>{`${items.length} findings`}</Tag>
          <Tag color="red">{`${counts.error} errors`}</Tag>
          <Tag color="gold">{`${counts.warning} warnings`}</Tag>
        </Space>
        <Space wrap style={{ marginTop: 12 }}>
          <Typography.Text type="secondary">Severity</Typography.Text>
          <Tag.CheckableTag
            checked={severityFilter === "all"}
            onChange={() => setSeverityFilter("all")}
          >
            All
          </Tag.CheckableTag>
          <Tag.CheckableTag
            checked={severityFilter === "error"}
            onChange={() => setSeverityFilter("error")}
          >
            Errors
          </Tag.CheckableTag>
          <Tag.CheckableTag
            checked={severityFilter === "warning"}
            onChange={() => setSeverityFilter("warning")}
          >
            Warnings
          </Tag.CheckableTag>
        </Space>
        <Space wrap style={{ marginTop: 8 }}>
          <Typography.Text type="secondary">Type</Typography.Text>
          <Tag.CheckableTag
            checked={findingTypeFilter === "all"}
            onChange={() => setFindingTypeFilter("all")}
          >
            All
          </Tag.CheckableTag>
          <Tag.CheckableTag
            checked={findingTypeFilter === "assignment_validation_blocker"}
            onChange={() => setFindingTypeFilter("assignment_validation_blocker")}
          >
            Assignment blockers
          </Tag.CheckableTag>
          <Tag.CheckableTag
            checked={findingTypeFilter === "workspace_source_readiness_warning"}
            onChange={() => setFindingTypeFilter("workspace_source_readiness_warning")}
          >
            Multi-root readiness
          </Tag.CheckableTag>
          <Tag.CheckableTag
            checked={findingTypeFilter === "external_server_configuration_issue"}
            onChange={() => setFindingTypeFilter("external_server_configuration_issue")}
          >
            External config
          </Tag.CheckableTag>
        </Space>
      </Card>

      <List
        bordered
        loading={loading}
        dataSource={items}
        locale={{ emptyText: <Empty description="No governance findings" /> }}
        renderItem={(finding) => (
          <List.Item
            actions={[
              <Button
                key="open"
                size="small"
                onClick={() => onOpen?.(finding.navigate_to)}
              >
                Open
              </Button>
            ]}
          >
            <Space orientation="vertical" size={4} style={{ width: "100%" }}>
              <Space wrap>
                <Typography.Text strong>{finding.object_label}</Typography.Text>
                <Tag color={severityColor(finding.severity)}>{finding.severity}</Tag>
                <Tag>{finding.finding_type}</Tag>
                <Tag>{finding.object_kind}</Tag>
                <Tag>{finding.scope_type}</Tag>
                {finding.scope_id !== null && finding.scope_id !== undefined ? (
                  <Tag>{`scope ${finding.scope_id}`}</Tag>
                ) : null}
              </Space>
              <Typography.Text>{finding.message}</Typography.Text>
              {finding.related_object_label ? (
                <Typography.Text type="secondary">
                  {`Related: ${finding.related_object_label}`}
                </Typography.Text>
              ) : null}
            </Space>
          </List.Item>
        )}
      />
    </Space>
  )
}
