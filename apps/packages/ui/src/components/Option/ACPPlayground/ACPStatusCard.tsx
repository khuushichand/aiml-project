import React from "react"
import { useTranslation } from "react-i18next"
import { useQuery } from "@tanstack/react-query"
import { Bot, Check, X, AlertCircle, Loader2 } from "lucide-react"
import { useCanonicalConnectionConfig } from "@/hooks/useCanonicalConnectionConfig"
import { buildACPAuthHeaders } from "@/services/acp/connection"

interface ACPHealthResponse {
  overall: string
  runner?: {
    status: string
    agent_type?: string
  }
  agents?: Array<{
    agent_type: string
    status: string
  }>
  [key: string]: unknown
}

/**
 * ACPStatusCard - Displays ACP backend health status.
 *
 * Fetches `/api/v1/acp/health` and shows runner status,
 * configured agent count, and overall availability.
 */
export const ACPStatusCard: React.FC = () => {
  const { t } = useTranslation(["playground", "common"])
  const { config: connectionConfig } = useCanonicalConnectionConfig()

  const {
    data: healthData,
    isLoading,
    isError,
  } = useQuery<ACPHealthResponse>({
    queryKey: ["acp", "health", "status-card"],
    queryFn: async () => {
      const resp = await fetch(
        `${connectionConfig!.serverUrl}/api/v1/acp/health`,
        { headers: buildACPAuthHeaders(connectionConfig) }
      )
      if (!resp.ok) {
        throw new Error(`Health check failed: ${resp.status}`)
      }
      return resp.json()
    },
    enabled: !!connectionConfig,
    staleTime: 30_000,
    refetchInterval: 60_000,
  })

  const isHealthy =
    healthData?.overall === "healthy" || healthData?.overall === "degraded"
  const isDegraded = healthData?.overall === "degraded"
  const agentCount = Array.isArray(healthData?.agents)
    ? healthData.agents.length
    : 0

  // Loading state
  if (isLoading) {
    return (
      <div className="rounded-lg border border-border bg-surface p-4">
        <div className="flex items-center gap-3">
          <Loader2 className="h-5 w-5 animate-spin text-text-muted" />
          <span className="text-sm text-text-muted">
            {t("playground:acp.statusCard.loading", "Checking ACP status...")}
          </span>
        </div>
      </div>
    )
  }

  // Error / unavailable state
  if (isError || !healthData || healthData.overall === "unavailable") {
    return (
      <div className="rounded-lg border border-border bg-surface p-4">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-error/10">
            <X className="h-4 w-4 text-error" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-sm font-medium text-text">
              {t("playground:acp.statusCard.unavailable", "ACP Unavailable")}
            </div>
            <div className="mt-0.5 text-xs text-text-muted">
              {t(
                "playground:acp.statusCard.unavailableHelp",
                "The ACP runner is not reachable. Check that the backend is running and ACP is enabled in your configuration."
              )}
            </div>
          </div>
        </div>
      </div>
    )
  }

  // Healthy / degraded state
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex items-center gap-3">
        <div
          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
            isDegraded ? "bg-warning/10" : "bg-success/10"
          }`}
        >
          {isDegraded ? (
            <AlertCircle className="h-4 w-4 text-warning" />
          ) : (
            <Check className="h-4 w-4 text-success" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium text-text">
            {isDegraded
              ? t("playground:acp.statusCard.degraded", "ACP Degraded")
              : t("playground:acp.statusCard.healthy", "ACP Healthy")}
          </div>
          <div className="mt-0.5 text-xs text-text-muted">
            {t(
              "playground:acp.statusCard.runnerStatus",
              "Runner: {{status}}",
              { status: healthData.runner?.status ?? healthData.overall }
            )}
            {agentCount > 0 && (
              <>
                {" "}
                &middot;{" "}
                {t(
                  "playground:acp.statusCard.agentCount",
                  "{{count}} agent(s) configured",
                  { count: agentCount }
                )}
              </>
            )}
          </div>
        </div>
        <Bot className="h-5 w-5 shrink-0 text-text-muted" />
      </div>
    </div>
  )
}

export default ACPStatusCard
