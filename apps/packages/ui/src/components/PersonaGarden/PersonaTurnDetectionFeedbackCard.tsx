import React from "react"

import {
  derivePersonaTurnDetectionPreset,
  type PersonaTurnDetectionValues
} from "@/components/PersonaGarden/PersonaTurnDetectionControls"
import type {
  PersonaLiveVoiceSessionSummary,
  PersonaVoiceAnalytics
} from "@/components/PersonaGarden/CommandAnalyticsSummary"

type PersonaTurnDetectionFeedbackCardProps = {
  analytics?: PersonaVoiceAnalytics | null
  loading?: boolean
}

type SuggestionDescriptor = {
  heading: string
  body: string
}

const MIN_RECENT_SESSIONS = 3
const MIN_ELIGIBLE_SESSIONS = 2
const MIN_ELIGIBLE_COMMITTED_TURNS = 8
const FAST_MANUAL_RATE_THRESHOLD = 0.35
const FAST_LISTENING_RECOVERY_RATE_MAX = 0.15
const THINKING_RECOVERY_RATE_THRESHOLD = 0.3
const HEALTHY_AUTO_RATE_THRESHOLD = 0.7
const HEALTHY_MANUAL_RATE_THRESHOLD = 0.15
const HEALTHY_RECOVERY_RATE_THRESHOLD = 0.15

const clampToNonNegativeNumber = (value: number): number =>
  Math.max(0, Number(value) || 0)

const clampToNonNegativeInteger = (value: number): number =>
  Math.max(0, Math.trunc(Number(value) || 0))

const formatPercent = (value: number): string =>
  `${Math.round(Math.min(1, Math.max(0, Number(value) || 0)) * 100)}%`

const formatDateTime = (value?: string | null): string => {
  const normalized = String(value || "").trim()
  if (!normalized) return "Session timing unavailable"
  const parsed = new Date(normalized)
  if (Number.isNaN(parsed.getTime())) return normalized
  return parsed.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit"
  })
}

const pluralize = (count: number, singular: string, plural: string): string =>
  `${count} ${count === 1 ? singular : plural}`

const getCommittedTurnCount = (session: PersonaLiveVoiceSessionSummary): number =>
  clampToNonNegativeInteger(session.total_committed_turns)

const sumCounts = (
  sessions: PersonaLiveVoiceSessionSummary[],
  selector: (session: PersonaLiveVoiceSessionSummary) => number
): number =>
  sessions.reduce((total, session) => total + Math.max(0, selector(session)), 0)

const divide = (numerator: number, denominator: number): number =>
  denominator > 0 ? numerator / denominator : 0

const buildTurnDetectionValues = (
  session: PersonaLiveVoiceSessionSummary
): PersonaTurnDetectionValues => ({
  autoCommitEnabled: Boolean(session.auto_commit_enabled),
  vadThreshold: clampToNonNegativeNumber(session.vad_threshold),
  minSilenceMs: clampToNonNegativeInteger(session.min_silence_ms),
  turnStopSecs: clampToNonNegativeNumber(session.turn_stop_secs),
  minUtteranceSecs: clampToNonNegativeNumber(session.min_utterance_secs)
})

const formatPresetLabel = (preset: ReturnType<typeof derivePersonaTurnDetectionPreset>): string =>
  preset === "custom"
    ? "Custom"
    : `${preset.slice(0, 1).toUpperCase()}${preset.slice(1)}`

const buildSuggestion = (
  recentSessions: PersonaLiveVoiceSessionSummary[]
): SuggestionDescriptor => {
  const eligibleSessions = recentSessions.filter(
    (session) => !session.turn_detection_changed_during_session
  )
  const eligibleCommittedTurns = sumCounts(eligibleSessions, getCommittedTurnCount)
  const eligibleAutoCommits = sumCounts(
    eligibleSessions,
    (session) => session.vad_auto_commit_count
  )
  const eligibleManualCommits = sumCounts(
    eligibleSessions,
    (session) => session.manual_commit_count
  )
  const eligibleManualModeRequired = sumCounts(
    eligibleSessions,
    (session) => session.manual_mode_required_count
  )
  const eligibleListeningRecovery = sumCounts(
    eligibleSessions,
    (session) => session.listening_recovery_count
  )
  const eligibleThinkingRecovery = sumCounts(
    eligibleSessions,
    (session) => session.thinking_recovery_count
  )
  const eligibleRecoveryCount = eligibleListeningRecovery + eligibleThinkingRecovery
  const autoRate = divide(eligibleAutoCommits, eligibleCommittedTurns)
  const manualRate = divide(eligibleManualCommits, eligibleCommittedTurns)
  const listeningRecoveryRate = divide(
    eligibleListeningRecovery,
    eligibleCommittedTurns
  )
  const thinkingRecoveryRate = divide(eligibleThinkingRecovery, eligibleCommittedTurns)
  const recoveryRate = divide(eligibleRecoveryCount, eligibleCommittedTurns)

  if (
    recentSessions.length < MIN_RECENT_SESSIONS ||
    eligibleSessions.length < MIN_ELIGIBLE_SESSIONS ||
    eligibleCommittedTurns < MIN_ELIGIBLE_COMMITTED_TURNS
  ) {
    return {
      heading: "No tuning suggestion yet",
      body: "Run a few live sessions to unlock guidance."
    }
  }

  if (eligibleManualModeRequired > 0) {
    return {
      heading: "Suggestion: check auto-commit availability first",
      body:
        "Recent sessions fell back to manual send because server auto-commit was unavailable."
    }
  }

  if (thinkingRecoveryRate >= THINKING_RECOVERY_RATE_THRESHOLD) {
    return {
      heading: "Suggestion: current turn detection may be fine",
      body:
        "Most delays happened after commit, which points to assistant/runtime latency rather than speech cutoff timing."
    }
  }

  if (
    manualRate >= FAST_MANUAL_RATE_THRESHOLD &&
    listeningRecoveryRate <= FAST_LISTENING_RECOVERY_RATE_MAX
  ) {
    return {
      heading: "Suggestion: try Fast for quicker commits",
      body:
        "Recent sessions needed manual sends often, but auto-commit availability looks healthy."
    }
  }

  if (
    autoRate >= HEALTHY_AUTO_RATE_THRESHOLD &&
    manualRate <= HEALTHY_MANUAL_RATE_THRESHOLD &&
    recoveryRate <= HEALTHY_RECOVERY_RATE_THRESHOLD
  ) {
    return {
      heading: "Suggestion: current settings look healthy",
      body: "Recent sessions show strong auto-commit performance with low recovery pressure."
    }
  }

  return {
    heading: "No tuning suggestion yet",
    body: "Recent sessions are still mixed, so the safest next step is to gather more live runs."
  }
}

export const PersonaTurnDetectionFeedbackCard: React.FC<
  PersonaTurnDetectionFeedbackCardProps
> = ({ analytics, loading = false }) => {
  const recentSessions = React.useMemo(
    () =>
      Array.isArray(analytics?.recent_live_sessions)
        ? analytics.recent_live_sessions.slice(0, 8)
        : [],
    [analytics]
  )
  const eligibleSessions = recentSessions.filter(
    (session) => !session.turn_detection_changed_during_session
  )
  const signalSessions = eligibleSessions.length > 0 ? eligibleSessions : recentSessions
  const mixedSessionCount = recentSessions.length - eligibleSessions.length
  const signalCommittedTurns = sumCounts(signalSessions, getCommittedTurnCount)
  const signalAutoCommits = sumCounts(signalSessions, (session) => session.vad_auto_commit_count)
  const signalManualCommits = sumCounts(signalSessions, (session) => session.manual_commit_count)
  const signalRecoveryCount = sumCounts(
    signalSessions,
    (session) => session.listening_recovery_count + session.thinking_recovery_count
  )
  const suggestion = buildSuggestion(recentSessions)

  if (!loading && !analytics && recentSessions.length === 0) return null

  return (
    <div
      data-testid="persona-turn-detection-feedback-card"
      className="mt-3 rounded-md border border-border bg-surface2 p-3"
    >
      <div className="text-xs font-semibold uppercase tracking-wide text-text-subtle">
        Recent live tuning feedback
      </div>
      {loading && !analytics ? (
        <div className="mt-2 text-xs text-text-muted">
          Loading recent live tuning feedback...
        </div>
      ) : (
        <div className="mt-3 space-y-3">
          <div className="rounded-md border border-border/80 bg-bg px-3 py-2">
            <div className="text-xs font-medium text-text">Current signal</div>
            <div className="mt-2 grid gap-2 sm:grid-cols-3">
              <div>
                <div className="text-[11px] uppercase tracking-wide text-text-subtle">
                  Auto-commit rate
                </div>
                <div className="mt-1 text-sm font-medium text-text">
                  {formatPercent(divide(signalAutoCommits, signalCommittedTurns))}
                </div>
              </div>
              <div>
                <div className="text-[11px] uppercase tracking-wide text-text-subtle">
                  Manual sends
                </div>
                <div className="mt-1 text-sm font-medium text-text">
                  {formatPercent(divide(signalManualCommits, signalCommittedTurns))}
                </div>
              </div>
              <div>
                <div className="text-[11px] uppercase tracking-wide text-text-subtle">
                  Recovery signals
                </div>
                <div className="mt-1 text-sm font-medium text-text">
                  {formatPercent(divide(signalRecoveryCount, signalCommittedTurns))}
                </div>
              </div>
            </div>
            <div className="mt-2 text-xs text-text-muted">
              Based on {pluralize(signalSessions.length, "eligible session", "eligible sessions")}
              {signalCommittedTurns > 0 ? ` and ${pluralize(signalCommittedTurns, "committed turn", "committed turns")}` : ""}.
            </div>
            {mixedSessionCount > 0 ? (
              <div
                data-testid="persona-turn-detection-feedback-mixed-note"
                className="mt-2 text-xs text-amber-200"
              >
                {pluralize(mixedSessionCount, "mixed recent session", "mixed recent sessions")} excluded from suggestions because turn detection changed mid-session.
              </div>
            ) : null}
          </div>

          <div className="rounded-md border border-border/80 bg-bg px-3 py-2">
            <div className="text-xs font-medium text-text">Suggested adjustment</div>
            <div className="mt-2 text-sm font-medium text-text">{suggestion.heading}</div>
            <div className="mt-1 text-xs text-text-muted">{suggestion.body}</div>
          </div>

          <div className="rounded-md border border-border/80 bg-bg px-3 py-2">
            <div className="text-xs font-medium text-text">Recent sessions</div>
            {recentSessions.length === 0 ? (
              <div className="mt-2 text-xs text-text-muted">
                No recent live sessions yet.
              </div>
            ) : (
              <div className="mt-2 space-y-2">
                {recentSessions.map((session) => {
                  const preset = formatPresetLabel(
                    derivePersonaTurnDetectionPreset(buildTurnDetectionValues(session))
                  )
                  return (
                    <div
                      key={session.session_id}
                      className="rounded-md border border-border bg-surface px-3 py-2"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <div className="text-sm font-medium text-text">
                          {session.session_id}
                        </div>
                        <span className="rounded-full border border-border px-2 py-0.5 text-[11px] text-text-muted">
                          {preset}
                        </span>
                        {session.turn_detection_changed_during_session ? (
                          <span className="rounded-full border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-[11px] text-amber-200">
                            Mixed session
                          </span>
                        ) : null}
                      </div>
                      <div className="mt-1 text-[11px] text-text-muted">
                        {formatDateTime(session.started_at)}
                      </div>
                      <div className="mt-2 text-xs text-text-muted">
                        Auto {session.vad_auto_commit_count} • Manual {session.manual_commit_count} • Recovery{" "}
                        {session.listening_recovery_count + session.thinking_recovery_count}
                      </div>
                      <div className="mt-1 text-xs text-text-muted">
                        Threshold {session.vad_threshold} • Silence {session.min_silence_ms} ms • Minimum{" "}
                        {session.min_utterance_secs} s • Tail {session.turn_stop_secs} s
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
