import React, { useEffect, useState, useCallback, useMemo } from "react"
import { useTranslation } from "react-i18next"
import { useStorage } from "@plasmohq/storage/hook"
import { Alert, Button, Card, Spin, Tag, Tooltip, Empty, Badge } from "antd"
import {
  Bot,
  CheckCircle,
  XCircle,
  AlertTriangle,
  RefreshCw,
  Play,
  Settings,
  Heart,
} from "lucide-react"
import { ACPRestClient } from "@/services/acp/client"

type AgentEntry = {
  type: string
  name: string
  description: string
  status: "available" | "unavailable" | "requires_setup"
  reason?: string
  is_default?: boolean
}

type HealthStatus = {
  runner: string
  agent: string
  api_keys: string
  details?: string
}

export const AgentRegistryPage: React.FC = () => {
  const { t } = useTranslation(["option", "common"])

  const [serverUrl] = useStorage("serverUrl", "http://localhost:8000")
  const [authMode] = useStorage("authMode", "single-user")
  const [apiKey] = useStorage("apiKey", "")
  const [accessToken] = useStorage("accessToken", "")

  const [agents, setAgents] = useState<AgentEntry[]>([])
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [healthLoading, setHealthLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const restClient = useMemo(
    () =>
      new ACPRestClient({
        serverUrl,
        getAuthHeaders: async () => {
          const headers: Record<string, string> = {}
          if (authMode === "single-user" && apiKey) {
            headers["X-API-KEY"] = apiKey
          } else if (authMode === "multi-user" && accessToken) {
            headers.Authorization = `Bearer ${accessToken}`
          }
          return headers
        },
        getAuthParams: async () => ({
          token: authMode === "multi-user" && accessToken ? accessToken : undefined,
          api_key: authMode === "single-user" && apiKey ? apiKey : undefined,
        }),
      }),
    [serverUrl, authMode, apiKey, accessToken]
  )

  const fetchAgents = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await restClient.getAvailableAgents()
      setAgents(
        (response.agents ?? []).map((agent) => ({
          type: agent.type,
          name: agent.name,
          description: agent.description,
          status: agent.is_configured ? "available" : "requires_setup"
        }))
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load agents")
    } finally {
      setLoading(false)
    }
  }, [restClient])

  const fetchHealth = useCallback(async () => {
    setHealthLoading(true)
    try {
      const url = `${serverUrl}/api/v1/acp/health`
      const headers: Record<string, string> = { "Content-Type": "application/json" }
      if (authMode === "single-user" && apiKey) {
        headers["X-API-KEY"] = apiKey
      } else if (authMode === "multi-user" && accessToken) {
        headers.Authorization = `Bearer ${accessToken}`
      }
      const res = await fetch(url, { headers })
      if (res.ok) {
        setHealth(await res.json())
      }
    } catch {
      // Health check failure is not critical
    } finally {
      setHealthLoading(false)
    }
  }, [serverUrl, authMode, apiKey, accessToken])

  useEffect(() => {
    void fetchAgents()
    void fetchHealth()
  }, [fetchAgents, fetchHealth])

  const statusIcon = (status: string) => {
    switch (status) {
      case "available":
      case "ok":
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case "unavailable":
      case "missing":
      case "error":
        return <XCircle className="h-4 w-4 text-red-500" />
      default:
        return <AlertTriangle className="h-4 w-4 text-yellow-500" />
    }
  }

  const statusColor = (status: string): "success" | "error" | "warning" => {
    switch (status) {
      case "available":
      case "ok":
        return "success"
      case "unavailable":
      case "missing":
      case "error":
        return "error"
      default:
        return "warning"
    }
  }

  return (
    <div className="space-y-6">
      {/* Health Status */}
      <Card
        title={
          <span className="flex items-center gap-2">
            <Heart className="h-4 w-4" />
            ACP System Health
          </span>
        }
        extra={
          <Button
            size="small"
            icon={<RefreshCw className="h-3.5 w-3.5" />}
            onClick={() => {
              void fetchHealth()
              void fetchAgents()
            }}
          >
            Refresh
          </Button>
        }
      >
        {healthLoading ? (
          <div className="flex justify-center py-4">
            <Spin size="small" />
          </div>
        ) : health ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="flex items-center gap-2 rounded-lg border border-border p-3">
              {statusIcon(health.runner)}
              <div>
                <div className="text-xs text-muted-foreground">Runner Binary</div>
                <Tag color={statusColor(health.runner)}>{health.runner}</Tag>
              </div>
            </div>
            <div className="flex items-center gap-2 rounded-lg border border-border p-3">
              {statusIcon(health.agent)}
              <div>
                <div className="text-xs text-muted-foreground">Agent Status</div>
                <Tag color={statusColor(health.agent)}>{health.agent}</Tag>
              </div>
            </div>
            <div className="flex items-center gap-2 rounded-lg border border-border p-3">
              {statusIcon(health.api_keys)}
              <div>
                <div className="text-xs text-muted-foreground">API Keys</div>
                <Tag color={statusColor(health.api_keys)}>{health.api_keys}</Tag>
              </div>
            </div>
          </div>
        ) : (
          <Alert
            type="warning"
            message="Health check unavailable"
            description="Could not reach the ACP health endpoint. Ensure the server is running."
            showIcon
          />
        )}
        {health?.details && (
          <div className="mt-2 text-xs text-muted-foreground">{health.details}</div>
        )}
      </Card>

      {/* Error */}
      {error && (
        <Alert type="error" message={error} closable onClose={() => setError(null)} />
      )}

      {/* Agent List */}
      <Card
        title={
          <span className="flex items-center gap-2">
            <Bot className="h-4 w-4" />
            Registered Agents
            {!loading && (
              <Badge
                count={agents.length}
                style={{ backgroundColor: "var(--primary)" }}
              />
            )}
          </span>
        }
      >
        {loading ? (
          <div className="flex justify-center py-8">
            <Spin />
          </div>
        ) : agents.length === 0 ? (
          <Empty description="No agents registered" />
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {agents.map((agent) => (
              <AgentCard key={agent.type} agent={agent} />
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}

const AgentCard: React.FC<{ agent: AgentEntry }> = ({ agent }) => {
  const statusColor =
    agent.status === "available"
      ? "success"
      : agent.status === "requires_setup"
        ? "warning"
        : "error"

  const statusLabel =
    agent.status === "available"
      ? "Ready"
      : agent.status === "requires_setup"
        ? "Setup Required"
        : "Unavailable"

  return (
    <div className="rounded-lg border border-border p-4 transition-shadow hover:shadow-md">
      <div className="mb-2 flex items-start justify-between">
        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5 text-primary" />
          <h3 className="font-medium">{agent.name}</h3>
        </div>
        <div className="flex items-center gap-1">
          {agent.is_default && (
            <Tag color="blue" className="text-xs">
              Default
            </Tag>
          )}
          <Tag color={statusColor}>{statusLabel}</Tag>
        </div>
      </div>

      <p className="mb-3 text-sm text-muted-foreground">
        {agent.description || `Agent type: ${agent.type}`}
      </p>

      {agent.reason && (
        <div className="mb-3 rounded bg-yellow-50 p-2 text-xs text-yellow-700 dark:bg-yellow-900/20 dark:text-yellow-400">
          {agent.reason}
        </div>
      )}

      <div className="flex items-center gap-2">
        <Tooltip title={agent.status === "available" ? "Launch session" : statusLabel}>
          <Button
            size="small"
            type="primary"
            icon={<Play className="h-3 w-3" />}
            disabled={agent.status !== "available"}
            onClick={() => {
              // Navigate to ACP playground with this agent pre-selected
              window.location.hash = `/acp-playground?agent=${agent.type}`
            }}
          >
            Launch
          </Button>
        </Tooltip>
        <span className="text-xs text-muted-foreground">{agent.type}</span>
      </div>
    </div>
  )
}

export default AgentRegistryPage
