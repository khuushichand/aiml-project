import { useEffect, useState } from "react"
import { Alert, Card, Empty, List, Space, Typography } from "antd"

import {
  fetchMcpToolCatalogs,
  fetchMcpToolCatalogsViaDiscovery,
  type McpToolCatalog
} from "@/services/tldw/mcp"

type CatalogScope = "global" | "org" | "team"

const SCOPE_LABELS: Record<CatalogScope, string> = {
  global: "Global",
  org: "Org",
  team: "Team"
}

export const ToolCatalogsTab = () => {
  const [scope, setScope] = useState<CatalogScope>("global")
  const [catalogs, setCatalogs] = useState<McpToolCatalog[]>([])
  const [loading, setLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      setLoading(true)
      setErrorMessage(null)
      try {
        const discovered = await fetchMcpToolCatalogsViaDiscovery(scope)
        if (!cancelled && discovered.length > 0) {
          setCatalogs(discovered)
          return
        }
        const fallback = await fetchMcpToolCatalogs()
        if (!cancelled) {
          setCatalogs(fallback)
        }
      } catch {
        if (!cancelled) {
          setCatalogs([])
          setErrorMessage("Failed to load tool catalogs.")
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
  }, [scope])

  return (
    <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
      <Typography.Text type="secondary">
        Tool catalogs control which MCP tools are exposed by scope.
      </Typography.Text>
      {errorMessage ? <Alert type="error" title={errorMessage} showIcon /> : null}

      <Space>
        <label htmlFor="mcp-catalog-scope">Scope</label>
        <select
          id="mcp-catalog-scope"
          aria-label="Scope"
          value={scope}
          onChange={(event) => setScope(event.target.value as CatalogScope)}
        >
          <option value="global">Global</option>
          <option value="org">Org</option>
          <option value="team">Team</option>
        </select>
      </Space>

      <Card title={`${SCOPE_LABELS[scope]} Catalogs`}>
        <List
          loading={loading}
          dataSource={catalogs}
          locale={{ emptyText: <Empty description="No catalogs available" /> }}
          renderItem={(catalog) => (
            <List.Item>
              <Space orientation="vertical" size={2}>
                <Typography.Text strong>{catalog.name}</Typography.Text>
                <Typography.Text type="secondary">
                  {catalog.description || "No description"}
                </Typography.Text>
              </Space>
            </List.Item>
          )}
        />
      </Card>
    </Space>
  )
}
