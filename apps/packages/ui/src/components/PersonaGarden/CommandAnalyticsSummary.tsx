import React from "react"

export type PersonaVoiceCommandAnalyticsItem = {
  command_id: string
  command_name?: string | null
  total_invocations: number
  success_count: number
  error_count: number
  avg_response_time_ms: number
  last_used?: string | null
}

export type PersonaVoiceFallbackAnalytics = {
  total_invocations: number
  success_count: number
  error_count: number
  avg_response_time_ms: number
  last_used?: string | null
}

export type PersonaVoiceAnalyticsSummaryData = {
  total_events: number
  direct_command_count: number
  planner_fallback_count: number
  success_rate: number
  fallback_rate: number
  avg_response_time_ms: number
}

export type PersonaVoiceAnalytics = {
  persona_id: string
  summary: PersonaVoiceAnalyticsSummaryData
  commands: PersonaVoiceCommandAnalyticsItem[]
  fallbacks: PersonaVoiceFallbackAnalytics
}

type CommandAnalyticsSummaryProps = {
  analytics?: PersonaVoiceAnalytics | null
  loading?: boolean
}

const formatPercent = (value: number): string => `${Math.round(Number(value) || 0)}%`

export const formatRunLabel = (count: number): string => {
  const normalized = Math.max(0, Math.trunc(Number(count) || 0))
  return `${normalized} ${normalized === 1 ? "run" : "runs"}`
}

export const formatFailureLabel = (count: number): string => {
  const normalized = Math.max(0, Math.trunc(Number(count) || 0))
  return `${normalized} ${normalized === 1 ? "failure" : "failures"}`
}

export const formatLastUsedLabel = (value?: string | null): string | null => {
  const normalized = String(value || "").trim()
  if (!normalized) return null
  const parsed = new Date(normalized)
  if (Number.isNaN(parsed.getTime())) {
    return "Recent activity recorded"
  }
  return `Last used ${parsed.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit"
  })}`
}

export const CommandAnalyticsSummary: React.FC<CommandAnalyticsSummaryProps> = ({
  analytics,
  loading = false
}) => {
  if (!loading && !analytics) return null

  const summary = analytics?.summary
  const fallbackCount = analytics?.fallbacks?.total_invocations || 0

  return (
    <div
      data-testid="persona-command-analytics-summary"
      className="rounded-md border border-border bg-bg p-3"
    >
      <div className="text-xs font-medium text-text">Recent live usage</div>
      {loading && !analytics ? (
        <div className="mt-2 text-xs text-text-muted">Loading analytics...</div>
      ) : (
        <div className="mt-2 space-y-3">
          <div className="grid gap-2 sm:grid-cols-3">
            <div className="rounded-md border border-border bg-surface px-3 py-2">
              <div className="text-[11px] uppercase tracking-wide text-text-subtle">
                Live runs
              </div>
              <div
                data-testid="persona-command-analytics-total-events"
                className="mt-1 text-lg font-semibold text-text"
              >
                {summary?.total_events ?? 0}
              </div>
            </div>
            <div className="rounded-md border border-border bg-surface px-3 py-2">
              <div className="text-[11px] uppercase tracking-wide text-text-subtle">
                Success rate
              </div>
              <div
                data-testid="persona-command-analytics-success-rate"
                className="mt-1 text-lg font-semibold text-text"
              >
                {formatPercent(summary?.success_rate ?? 0)}
              </div>
            </div>
            <div className="rounded-md border border-border bg-surface px-3 py-2">
              <div className="text-[11px] uppercase tracking-wide text-text-subtle">
                Fallback rate
              </div>
              <div
                data-testid="persona-command-analytics-fallback-rate"
                className="mt-1 text-lg font-semibold text-text"
              >
                {formatPercent(summary?.fallback_rate ?? 0)}
              </div>
            </div>
          </div>
          <div
            data-testid="persona-command-analytics-fallback-note"
            className="text-xs text-text-muted"
          >
            {fallbackCount > 0
              ? `${fallbackCount} planner fallbacks in the last 7 days`
              : "No planner fallbacks recorded in the last 7 days"}
          </div>
        </div>
      )}
    </div>
  )
}
