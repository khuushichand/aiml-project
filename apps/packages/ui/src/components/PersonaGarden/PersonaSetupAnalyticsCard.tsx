import React from "react"
import { useTranslation } from "react-i18next"

export type PersonaSetupAnalyticsSummary = {
  total_runs: number
  completed_runs: number
  completion_rate: number
  dry_run_completion_count: number
  live_session_completion_count: number
  most_common_dropoff_step: string | null
  handoff_click_rate: number
  handoff_target_reach_rate: number
  first_post_setup_action_rate: number
  handoff_target_reached_counts: Record<string, number>
  detour_started_counts: Record<string, number>
  detour_returned_counts: Record<string, number>
}

export type PersonaSetupAnalyticsRunSummary = {
  run_id: string
  started_at?: string | null
  completed_at?: string | null
  completion_type?: "dry_run" | "live_session" | null
  terminal_step?: string | null
  handoff_clicked: boolean
  handoff_target_reached: boolean
  handoff_dismissed: boolean
  first_post_setup_action: boolean
}

export type PersonaSetupAnalyticsResponse = {
  persona_id: string
  summary: PersonaSetupAnalyticsSummary
  recent_runs: PersonaSetupAnalyticsRunSummary[]
}

type PersonaSetupAnalyticsCardProps = {
  analytics?: PersonaSetupAnalyticsResponse | null
  loading?: boolean
}

const DROP_OFF_LABELS: Record<string, string> = {
  persona: "Persona choice",
  voice: "Voice defaults",
  commands: "Starter commands",
  safety: "Safety and connections",
  test: "Test and finish"
}

const formatPercent = (value: number): string =>
  `${Math.round(Math.min(1, Math.max(0, Number(value) || 0)) * 100)}%`

const formatDropoffStep = (value: string | null | undefined): string => {
  const normalized = String(value || "").trim()
  if (!normalized) return "None yet"
  if (DROP_OFF_LABELS[normalized]) return DROP_OFF_LABELS[normalized]
  const readable = normalized.replace(/[_-]+/g, " ").trim()
  if (!readable) return "None yet"
  return readable.charAt(0).toUpperCase() + readable.slice(1).toLowerCase()
}

const Stat: React.FC<{ label: string; value: string | number }> = ({ label, value }) => (
  <div>
    <div className="text-[11px] uppercase tracking-wide text-text-subtle">{label}</div>
    <div className="mt-1 text-sm font-medium text-text">{value}</div>
  </div>
)

export const PersonaSetupAnalyticsCard: React.FC<PersonaSetupAnalyticsCardProps> = ({
  analytics = null,
  loading = false
}) => {
  const { t } = useTranslation(["sidepanel", "common"])

  if (loading && !analytics) {
    return (
      <div
        data-testid="persona-setup-analytics-card"
        className="rounded-lg border border-border bg-surface p-3"
      >
        <div className="text-xs font-semibold uppercase tracking-wide text-text-subtle">
          {t("sidepanel:personaGarden.profile.setupAnalyticsHeading", {
            defaultValue: "Setup analytics"
          })}
        </div>
        <div className="mt-2 text-xs text-text-muted">
          {t("sidepanel:personaGarden.profile.setupAnalyticsLoading", {
            defaultValue: "Loading setup analytics..."
          })}
        </div>
      </div>
    )
  }

  const summary = analytics?.summary
  if (!summary || summary.total_runs <= 0) return null

  return (
    <div
      data-testid="persona-setup-analytics-card"
      className="rounded-lg border border-border bg-surface p-3"
    >
      <div className="text-xs font-semibold uppercase tracking-wide text-text-subtle">
        {t("sidepanel:personaGarden.profile.setupAnalyticsHeading", {
          defaultValue: "Setup analytics"
        })}
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <Stat
          label={t("sidepanel:personaGarden.profile.setupAnalyticsCompletionRate", {
            defaultValue: "Completion rate"
          })}
          value={formatPercent(summary.completion_rate)}
        />
        <Stat
          label={t("sidepanel:personaGarden.profile.setupAnalyticsDropoff", {
            defaultValue: "Most common drop-off"
          })}
          value={formatDropoffStep(summary.most_common_dropoff_step)}
        />
        <Stat
          label={t("sidepanel:personaGarden.profile.setupAnalyticsDryRunCompletions", {
            defaultValue: "Dry run completions"
          })}
          value={summary.dry_run_completion_count}
        />
        <Stat
          label={t("sidepanel:personaGarden.profile.setupAnalyticsLiveCompletions", {
            defaultValue: "Live session completions"
          })}
          value={summary.live_session_completion_count}
        />
        <Stat
          label={t("sidepanel:personaGarden.profile.setupAnalyticsHandoffClicks", {
            defaultValue: "Handoff click rate"
          })}
          value={formatPercent(summary.handoff_click_rate)}
        />
        <Stat
          label={t("sidepanel:personaGarden.profile.setupAnalyticsTargetReached", {
            defaultValue: "Target reached rate"
          })}
          value={formatPercent(summary.handoff_target_reach_rate)}
        />
        <Stat
          label={t("sidepanel:personaGarden.profile.setupAnalyticsFirstAction", {
            defaultValue: "First next-step rate"
          })}
          value={formatPercent(summary.first_post_setup_action_rate)}
        />
      </div>
    </div>
  )
}
