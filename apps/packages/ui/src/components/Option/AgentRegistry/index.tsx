import React, { useEffect, useState, useCallback, useMemo } from "react"
import { useTranslation } from "react-i18next"
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
import { useCanonicalConnectionConfig } from "@/hooks/useCanonicalConnectionConfig"
import { ACPRestClient } from "@/services/acp/client"
import { resolveBrowserRequestTransport } from "@/services/tldw/request-core"

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

const formatHealthDetails = (
  message: unknown,
  runner: Record<string, unknown> | null,
  availableAgents: number,
  totalAgents: number
): string | undefined => {
  const parts: string[] = []
  if (typeof message === "string" && message.trim().length > 0) {
    parts.push(message.trim())
  }
  if (runner) {
    const source = typeof runner.source === "string" ? runner.source : null
    const path = typeof runner.path === "string" ? runner.path : null
    const runnerParts = [
      "Runner",
      source ? `source ${source}` : null,
      path ? `path ${path}` : null
    ].filter((part): part is string => Boolean(part))
    if (runnerParts.length > 1) {
      parts.push(runnerParts.join(" "))
    }
  }
  if (totalAgents > 0) {
    parts.push(`${availableAgents}/${totalAgents} agents available`)
  }
  return parts.length > 0 ? parts.join(" • ") : undefined
}

const normalizeHealthStatus = (payload: unknown): HealthStatus | null => {
  if (!payload || typeof payload !== "object") {
    return null
  }

  const record = payload as Record<string, unknown>
  if (
    typeof record.runner === "string" &&
    typeof record.agent === "string" &&
    typeof record.api_keys === "string"
  ) {
    return {
      runner: record.runner,
      agent: record.agent,
      api_keys: record.api_keys,
      details: typeof record.details === "string" ? record.details : undefined
    }
  }

  const runner =
    record.runner && typeof record.runner === "object" && !Array.isArray(record.runner)
      ? (record.runner as Record<string, unknown>)
      : null
  const agents = Array.isArray(record.agents)
    ? record.agents.filter(
        (agent): agent is Record<string, unknown> =>
          Boolean(agent) && typeof agent === "object" && !Array.isArray(agent)
      )
    : []
  const availableAgents = agents.filter((agent) => agent.status === "available").length
  const missingApiKeys = agents.some((agent) => agent.api_key_set === false)

  return {
    runner: typeof runner?.status === "string" ? runner.status : "unknown",
    agent:
      agents.length === 0
        ? typeof record.overall === "string"
          ? record.overall
          : "unknown"
        : availableAgents === 0
          ? "unavailable"
          : availableAgents === agents.length
            ? "available"
            : "degraded",
    api_keys: missingApiKeys ? "missing" : "ok",
    details: formatHealthDetails(record.message, runner, availableAgents, agents.length)
  }
}

export const AgentRegistryPage: React.FC = () => {
  const { t } = useTranslation(["option", "common"])
  const { config: connectionConfig } = useCanonicalConnectionConfig()

  const [agents, setAgents] = useState<AgentEntry[]>([])
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [healthLoading, setHealthLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const restClient = useMemo(
    () =>
      connectionConfig
        ? new ACPRestClient({
            serverUrl: connectionConfig.serverUrl,
            getAuthHeaders: async () => {
              const headers: Record<string, string> = {}
              if (connectionConfig.authMode === "single-user" && connectionConfig.apiKey) {
                headers["X-API-KEY"] = connectionConfig.apiKey
              } else if (
                connectionConfig.authMode === "multi-user" &&
                connectionConfig.accessToken
              ) {
                headers.Authorization = `Bearer ${connectionConfig.accessToken}`
              }
              if (typeof connectionConfig.orgId === "number") {
                headers["X-TLDW-Org-Id"] = String(connectionConfig.orgId)
              }
              return headers
            },
            getAuthParams: async () => ({
              token:
                connectionConfig.authMode === "multi-user" && connectionConfig.accessToken
                  ? connectionConfig.accessToken
                  : undefined,
              api_key:
                connectionConfig.authMode === "single-user" && connectionConfig.apiKey
                  ? connectionConfig.apiKey
                  : undefined,
            }),
          })
        : null,
    [connectionConfig]
  )

  const fetchAgents = useCallback(async () => {
    if (!restClient) return
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
    if (!connectionConfig) return
    setHealthLoading(true)
    try {
      const transport = resolveBrowserRequestTransport({
        config: connectionConfig,
        path: "/api/v1/acp/health"
      })
      const headers: Record<string, string> = { "Content-Type": "application/json" }
      if (
        transport.mode !== "hosted" &&
        connectionConfig.authMode === "single-user" &&
        connectionConfig.apiKey
      ) {
        headers["X-API-KEY"] = connectionConfig.apiKey
      } else if (
        transport.mode !== "hosted" &&
        connectionConfig.authMode === "multi-user" &&
        connectionConfig.accessToken
      ) {
        headers.Authorization = `Bearer ${connectionConfig.accessToken}`
      }
      if (transport.mode !== "hosted" && typeof connectionConfig.orgId === "number") {
        headers["X-TLDW-Org-Id"] = String(connectionConfig.orgId)
      }
      const res = await fetch(transport.url, { headers })
      if (res.ok) {
        setHealth(normalizeHealthStatus(await res.json()))
      }
    } catch {
      // Health check failure is not critical
    } finally {
      setHealthLoading(false)
    }
  }, [connectionConfig])

  useEffect(() => {
    if (!connectionConfig) return
    void fetchAgents()
    void fetchHealth()
  }, [connectionConfig, fetchAgents, fetchHealth])

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
