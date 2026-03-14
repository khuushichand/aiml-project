import { useEffect, useMemo, useState } from "react"
import { Alert, Card, Empty, Space, Tag, Typography } from "antd"

import {
  getToolRegistrySummary,
  type McpHubToolRegistryEntry,
  type McpHubToolRegistryModule
} from "@/services/tldw/mcp-hub"

import { getPathScopeLabel, getToolEntriesByModule } from "./policyHelpers"

export const ToolCatalogsTab = () => {
  const [entries, setEntries] = useState<McpHubToolRegistryEntry[]>([])
  const [modules, setModules] = useState<McpHubToolRegistryModule[]>([])
  const [loading, setLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const groupedModules = useMemo(() => getToolEntriesByModule(entries, modules), [entries, modules])

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      setLoading(true)
      setErrorMessage(null)
      try {
        const summary = await getToolRegistrySummary()
        if (!cancelled) {
          setEntries(Array.isArray(summary?.entries) ? summary.entries : [])
          setModules(Array.isArray(summary?.modules) ? summary.modules : [])
        }
      } catch {
        if (!cancelled) {
          setEntries([])
          setModules([])
          setErrorMessage("Failed to load tool registry metadata.")
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

  return (
    <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
      <Typography.Text type="secondary">
        Registry-backed tool metadata powers both the catalog view and the guided policy editor.
      </Typography.Text>
      {errorMessage ? <Alert type="error" title={errorMessage} showIcon /> : null}

      {groupedModules.length > 0 ? (
        groupedModules.map((module) => (
          <Card
            key={module.module}
            title={
              <Space wrap>
                <Typography.Text strong>{module.display_name}</Typography.Text>
                <Tag>{`${module.tool_count} tools`}</Tag>
                {Object.entries(module.risk_summary)
                  .filter(([, count]) => Number(count) > 0)
                  .map(([riskClass, count]) => (
                    <Tag key={`${module.module}-${riskClass}`}>{`${riskClass}:${count}`}</Tag>
                  ))}
              </Space>
            }
            loading={loading}
          >
            <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
              {module.metadata_warnings.length > 0 ? (
                <Alert type="warning" showIcon message={module.metadata_warnings.join(" ")} />
              ) : null}
              {module.tools.map((tool) => (
                <Card key={tool.tool_name} size="small">
                  <Space orientation="vertical" size={4} style={{ width: "100%" }}>
                    <Space wrap>
                      <Typography.Text strong>{tool.display_name}</Typography.Text>
                      <Tag>{tool.category}</Tag>
                      <Tag
                        color={
                          tool.risk_class === "high"
                            ? "red"
                            : tool.risk_class === "medium"
                              ? "gold"
                              : "green"
                        }
                      >
                        {tool.risk_class}
                      </Tag>
                      <Tag>{tool.metadata_source}</Tag>
                      {tool.mutates_state ? <Tag color="volcano">mutates</Tag> : null}
                      {tool.uses_network ? <Tag color="purple">network</Tag> : null}
                      {tool.uses_processes ? <Tag color="magenta">process</Tag> : null}
                      {tool.uses_filesystem && tool.path_boundable ? (
                        <Tag color="cyan">path-enforceable</Tag>
                      ) : null}
                      {tool.uses_filesystem && !tool.path_boundable ? (
                        <Tag color="orange">approval fallback</Tag>
                      ) : null}
                    </Space>
                    <Typography.Text type="secondary">
                      {tool.description || "No description"}
                    </Typography.Text>
                    <Space wrap>
                      {tool.capabilities.map((capability) => (
                        <Tag key={`${tool.tool_name}-${capability}`}>{capability}</Tag>
                      ))}
                      {tool.path_boundable && tool.path_argument_hints.length > 0 ? (
                        <Tag color="cyan">{`hints:${tool.path_argument_hints.join(", ")}`}</Tag>
                      ) : null}
                    </Space>
                    {tool.uses_filesystem && !tool.path_boundable ? (
                      <Alert
                        type="info"
                        showIcon
                        message={`Path-scoped profiles fall back to approval for ${tool.display_name}.`}
                        description={`This tool touches local files but is not yet marked as ${getPathScopeLabel("workspace_root")?.toLowerCase()} enforceable.`}
                      />
                    ) : null}
                    {tool.metadata_warnings.length > 0 ? (
                      <Alert type="warning" showIcon message={tool.metadata_warnings.join(" ")} />
                    ) : null}
                  </Space>
                </Card>
              ))}
            </Space>
          </Card>
        ))
      ) : (
        <Card loading={loading}>
          <Empty description="No registry metadata available yet" />
        </Card>
      )}
    </Space>
  )
}
