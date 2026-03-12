import { useEffect, useMemo, useState } from "react"
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

const FINDING_TYPE_ORDER: McpHubGovernanceAuditFindingType[] = [
  "assignment_validation_blocker",
  "workspace_source_readiness_warning",
  "shared_workspace_overlap_warning",
  "external_server_configuration_issue",
  "external_binding_issue"
]

const FINDING_TYPE_LABELS: Record<McpHubGovernanceAuditFindingType, string> = {
  assignment_validation_blocker: "Assignment blockers",
  workspace_source_readiness_warning: "Multi-root readiness",
  shared_workspace_overlap_warning: "Shared workspace overlap",
  external_server_configuration_issue: "External config",
  external_binding_issue: "External binding issues"
}

const OBJECT_KIND_LABELS: Record<string, string> = {
  policy_assignment: "Policy assignments",
  workspace_set_object: "Workspace sets",
  shared_workspace: "Shared workspaces",
  external_server: "External servers",
  permission_profile: "Permission profiles"
}

const _dedupe = (values: string[]) =>
  Array.from(new Set(values.filter((value) => value.trim().length > 0))).sort((a, b) =>
    a.localeCompare(b)
  )

export const GovernanceAuditTab = ({ onOpen }: GovernanceAuditTabProps) => {
  const [allItems, setAllItems] = useState<McpHubGovernanceAuditFinding[]>([])
  const [loading, setLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [severityFilter, setSeverityFilter] = useState<"all" | "error" | "warning">("all")
  const [findingTypeFilter, setFindingTypeFilter] = useState<"all" | McpHubGovernanceAuditFindingType>("all")
  const [objectKindFilter, setObjectKindFilter] = useState<"all" | string>("all")
  const [scopeTypeFilter, setScopeTypeFilter] = useState<"all" | string>("all")
  const [hasRelatedObjectOnly, setHasRelatedObjectOnly] = useState(false)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      setLoading(true)
      setErrorMessage(null)
      try {
        const result = await listGovernanceAuditFindings()
        if (!cancelled) {
          setAllItems(Array.isArray(result?.items) ? result.items : [])
        }
      } catch {
        if (!cancelled) {
          setAllItems([])
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
  }, [])

  const availableFindingTypes = useMemo(
    () => _dedupe(allItems.map((item) => String(item.finding_type || ""))),
    [allItems]
  )
  const availableObjectKinds = useMemo(
    () => _dedupe(allItems.map((item) => String(item.object_kind || ""))),
    [allItems]
  )
  const availableScopeTypes = useMemo(
    () => _dedupe(allItems.map((item) => String(item.scope_type || ""))),
    [allItems]
  )

  const filteredItems = useMemo(() => {
    return allItems.filter((item) => {
      if (severityFilter !== "all" && item.severity !== severityFilter) {
        return false
      }
      if (findingTypeFilter !== "all" && item.finding_type !== findingTypeFilter) {
        return false
      }
      if (objectKindFilter !== "all" && item.object_kind !== objectKindFilter) {
        return false
      }
      if (scopeTypeFilter !== "all" && item.scope_type !== scopeTypeFilter) {
        return false
      }
      if (
        hasRelatedObjectOnly &&
        !String(item.related_object_label || item.related_object_id || "").trim()
      ) {
        return false
      }
      return true
    })
  }, [
    allItems,
    severityFilter,
    findingTypeFilter,
    objectKindFilter,
    scopeTypeFilter,
    hasRelatedObjectOnly
  ])

  const filteredCounts = useMemo(
    () => ({
      error: filteredItems.filter((item) => item.severity === "error").length,
      warning: filteredItems.filter((item) => item.severity === "warning").length
    }),
    [filteredItems]
  )

  const groupedItems = useMemo(() => {
    const groups = new Map<McpHubGovernanceAuditFindingType, McpHubGovernanceAuditFinding[]>()
    for (const findingType of FINDING_TYPE_ORDER) {
      groups.set(findingType, [])
    }
    for (const item of filteredItems) {
      const bucket = groups.get(item.finding_type)
      if (bucket) {
        bucket.push(item)
      }
    }
    for (const [findingType, items] of groups.entries()) {
      items.sort((left, right) => {
        if (left.severity !== right.severity) {
          return left.severity === "error" ? -1 : 1
        }
        return String(left.object_label || "").localeCompare(String(right.object_label || ""))
      })
      groups.set(findingType, items)
    }
    return groups
  }, [filteredItems])

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
          <Tag>{`${filteredItems.length} findings`}</Tag>
          <Tag color="red">{`${filteredCounts.error} errors`}</Tag>
          <Tag color="gold">{`${filteredCounts.warning} warnings`}</Tag>
        </Space>
        <Space wrap style={{ marginTop: 12 }}>
          <Typography.Text type="secondary">Severity</Typography.Text>
          <Tag.CheckableTag
            checked={severityFilter === "all"}
            onChange={() => setSeverityFilter("all")}
            role="button"
            aria-label="All severities"
          >
            All
          </Tag.CheckableTag>
          <Tag.CheckableTag
            checked={severityFilter === "error"}
            onChange={() => setSeverityFilter("error")}
            role="button"
            aria-label="Error severities"
          >
            Errors
          </Tag.CheckableTag>
          <Tag.CheckableTag
            checked={severityFilter === "warning"}
            onChange={() => setSeverityFilter("warning")}
            role="button"
            aria-label="Warning severities"
          >
            Warnings
          </Tag.CheckableTag>
        </Space>
        <Space wrap style={{ marginTop: 8 }}>
          <Typography.Text type="secondary">Type</Typography.Text>
          <Tag.CheckableTag
            checked={findingTypeFilter === "all"}
            onChange={() => setFindingTypeFilter("all")}
            role="button"
            aria-label="All finding types"
          >
            All
          </Tag.CheckableTag>
          {FINDING_TYPE_ORDER.filter((findingType) =>
            availableFindingTypes.includes(findingType)
          ).map((findingType) => (
            <Tag.CheckableTag
              key={findingType}
              checked={findingTypeFilter === findingType}
              onChange={() => setFindingTypeFilter(findingType)}
              role="button"
              aria-label={`Finding type ${FINDING_TYPE_LABELS[findingType]}`}
            >
              {FINDING_TYPE_LABELS[findingType]}
            </Tag.CheckableTag>
          ))}
        </Space>
        <Space wrap style={{ marginTop: 8 }}>
          <Typography.Text type="secondary">Object Kind</Typography.Text>
          <Tag.CheckableTag
            checked={objectKindFilter === "all"}
            onChange={() => setObjectKindFilter("all")}
            role="button"
            aria-label="All object kinds"
          >
            All
          </Tag.CheckableTag>
          {availableObjectKinds.map((objectKind) => (
            <Tag.CheckableTag
              key={objectKind}
              checked={objectKindFilter === objectKind}
              onChange={() => setObjectKindFilter(objectKind)}
              role="button"
              aria-label={`Object kind ${OBJECT_KIND_LABELS[objectKind] || objectKind}`}
            >
              {OBJECT_KIND_LABELS[objectKind] || objectKind}
            </Tag.CheckableTag>
          ))}
        </Space>
        <Space wrap style={{ marginTop: 8 }}>
          <Typography.Text type="secondary">Scope</Typography.Text>
          <Tag.CheckableTag
            checked={scopeTypeFilter === "all"}
            onChange={() => setScopeTypeFilter("all")}
            role="button"
            aria-label="All scopes"
          >
            All
          </Tag.CheckableTag>
          {availableScopeTypes.map((scopeType) => (
            <Tag.CheckableTag
              key={scopeType}
              checked={scopeTypeFilter === scopeType}
              onChange={() => setScopeTypeFilter(scopeType)}
              role="button"
              aria-label={`Scope ${scopeType}`}
            >
              {scopeType}
            </Tag.CheckableTag>
          ))}
        </Space>
        <Space wrap style={{ marginTop: 8 }}>
          <Typography.Text type="secondary">Relationships</Typography.Text>
          <Tag.CheckableTag
            checked={hasRelatedObjectOnly}
            onChange={(checked) => setHasRelatedObjectOnly(checked)}
            role="button"
            aria-label="Has related object"
          >
            Has related object
          </Tag.CheckableTag>
        </Space>
      </Card>

      {filteredItems.length === 0 ? (
        <Card>
          <Empty description="No governance findings" />
        </Card>
      ) : null}

      {FINDING_TYPE_ORDER.map((findingType) => {
        const groupItems = groupedItems.get(findingType) || []
        if (groupItems.length === 0) {
          return null
        }
        return (
          <Card
            key={findingType}
            title={`${FINDING_TYPE_LABELS[findingType]} (${groupItems.length})`}
            data-testid={`audit-group-${findingType}`}
          >
            <List
              dataSource={groupItems}
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
                      <Tag>{finding.object_kind}</Tag>
                      <Tag>{finding.scope_type}</Tag>
                      {finding.scope_id !== null && finding.scope_id !== undefined ? (
                        <Tag>{`scope ${finding.scope_id}`}</Tag>
                      ) : null}
                    </Space>
                    <Typography.Text>{finding.message}</Typography.Text>
                    {finding.related_object_label ? (
                      <Typography.Text type="secondary">
                        {`Related to: ${finding.related_object_label}${
                          finding.related_object_kind
                            ? ` (${finding.related_object_kind})`
                            : ""
                        }`}
                      </Typography.Text>
                    ) : null}
                  </Space>
                </List.Item>
              )}
            />
          </Card>
        )
      })}
    </Space>
  )
}
