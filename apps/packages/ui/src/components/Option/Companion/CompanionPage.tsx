import React from "react"
import { Link } from "react-router-dom"
import { useTranslation } from "react-i18next"

import { useServerCapabilities } from "@/hooks/useServerCapabilities"
import { useServerOnline } from "@/hooks/useServerOnline"
import {
  createCompanionGoal,
  fetchCompanionKnowledgeDetail,
  fetchCompanionReflectionDetail,
  fetchPersonalizationProfile,
  fetchCompanionWorkspaceSnapshot,
  purgeCompanionScope,
  queueCompanionRebuild,
  recordCompanionCheckIn,
  setCompanionGoalStatus,
  type CompanionActivityItem,
  type CompanionGoal,
  type CompanionKnowledgeDetail,
  type CompanionLifecycleResponse,
  type CompanionLifecycleScope,
  type PersonalizationProfile,
  type CompanionReflection,
  type CompanionReflectionDetail,
  type CompanionWorkspaceSnapshot,
  updateCompanionPreferences,
  updatePersonalizationOptIn
} from "@/services/companion"

const formatTimestamp = (value: string): string => {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString()
}

const titleCase = (value: string): string =>
  value
    .split(/[_./:-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ")

const describeActivity = (item: CompanionActivityItem): string => {
  const rawTitle = item.metadata?.title
  if (typeof rawTitle === "string" && rawTitle.trim().length > 0) {
    return rawTitle.trim()
  }
  const rawSummary = item.metadata?.summary
  if (typeof rawSummary === "string" && rawSummary.trim().length > 0) {
    return rawSummary.trim()
  }
  return titleCase(item.event_type)
}

const parseTagInput = (value: string): string[] =>
  value
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean)

const summarizeProgress = (goal: CompanionGoal): string => {
  const completed = Number(goal.progress?.completed_count)
  const target =
    Number(goal.config?.target_count) ||
    Number(goal.progress?.target_count) ||
    Number(goal.progress?.target)
  if (Number.isFinite(completed) && Number.isFinite(target) && target > 0) {
    return `${completed} / ${target} complete`
  }
  if (Number.isFinite(completed)) {
    return `${completed} completed`
  }
  return "Progress tracked from explicit activity."
}

const lifecycleScopeLabel = (scope: CompanionLifecycleScope): string => {
  switch (scope) {
    case "knowledge":
      return "knowledge"
    case "reflections":
      return "reflections"
    case "derived_goals":
      return "derived goals"
    case "goal_progress":
      return "goal progress"
    default:
      return scope
  }
}

const reflectionInboxLabel = (
  reflection: CompanionReflection,
  snapshot: CompanionWorkspaceSnapshot
): string | null => {
  const linkedNotification = snapshot.reflectionNotifications.find(
    (item) => item.link_id === reflection.id
  )
  if (!linkedNotification) return null
  return linkedNotification.read_at ? "In inbox" : "New in inbox"
}

const normalizeFollowUpPrompts = (
  value: CompanionReflectionDetail["follow_up_prompts"]
): CompanionReflectionDetail["follow_up_prompts"] =>
  Array.isArray(value)
    ? value.filter(
        (item) =>
          item &&
          typeof item.prompt_text === "string" &&
          item.prompt_text.trim().length > 0
      )
    : []

type CompanionPageProps = {
  surface?: "options" | "sidepanel"
  onCompanionEnabled?: () => void
}

type CheckInFormState = {
  title: string
  summary: string
  tags: string
}

type GoalFormState = {
  title: string
  description: string
}

type ProvenanceState =
  | { kind: "knowledge"; detail: CompanionKnowledgeDetail }
  | { kind: "reflection"; detail: CompanionReflectionDetail }
  | null

type CompanionPreferenceToggleKey =
  | "proactive_enabled"
  | "companion_reflections_enabled"
  | "companion_daily_reflections_enabled"
  | "companion_weekly_reflections_enabled"

type PendingLifecycleAction =
  | {
      mode: "purge" | "rebuild"
      scope: CompanionLifecycleScope
    }
  | null

export const CompanionPage = ({
  surface = "options",
  onCompanionEnabled
}: CompanionPageProps) => {
  const { t } = useTranslation(["option", "common"])
  const isOnline = useServerOnline()
  const { capabilities, loading: capsLoading } = useServerCapabilities()

  const [snapshot, setSnapshot] = React.useState<CompanionWorkspaceSnapshot | null>(
    null
  )
  const [profile, setProfile] = React.useState<PersonalizationProfile | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const [reloadToken, setReloadToken] = React.useState(0)
  const [checkInForm, setCheckInForm] = React.useState<CheckInFormState>({
    title: "",
    summary: "",
    tags: ""
  })
  const [savingCheckIn, setSavingCheckIn] = React.useState(false)
  const [goalForm, setGoalForm] = React.useState<GoalFormState>({
    title: "",
    description: ""
  })
  const [creatingGoal, setCreatingGoal] = React.useState(false)
  const [updatingGoalId, setUpdatingGoalId] = React.useState<string | null>(null)
  const [enablingCompanion, setEnablingCompanion] = React.useState(false)
  const [savingPreferenceKey, setSavingPreferenceKey] =
    React.useState<CompanionPreferenceToggleKey | null>(null)
  const [provenance, setProvenance] = React.useState<ProvenanceState>(null)
  const [loadingProvenanceId, setLoadingProvenanceId] = React.useState<string | null>(
    null
  )
  const [pendingLifecycleAction, setPendingLifecycleAction] =
    React.useState<PendingLifecycleAction>(null)
  const [runningLifecycleAction, setRunningLifecycleAction] =
    React.useState<string | null>(null)
  const [lifecycleResult, setLifecycleResult] =
    React.useState<CompanionLifecycleResponse | null>(null)

  const updateCheckInForm = (field: keyof CheckInFormState, value: string) => {
    setCheckInForm((current) => ({
      ...current,
      [field]: value
    }))
  }

  const updateGoalForm = (field: keyof GoalFormState, value: string) => {
    setGoalForm((current) => ({
      ...current,
      [field]: value
    }))
  }

  React.useEffect(() => {
    if (!isOnline || capsLoading) return
    if (!capabilities?.hasPersonalization) {
      setLoading(false)
      setSnapshot(null)
      setProfile(null)
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)

    fetchPersonalizationProfile()
      .then(async (nextProfile) => {
        if (cancelled) return
        setProfile(nextProfile)
        if (!nextProfile.enabled) {
          setSnapshot(null)
          return
        }
        const nextSnapshot = await fetchCompanionWorkspaceSnapshot()
        if (cancelled) return
        setSnapshot(nextSnapshot)
      })
      .catch((nextError) => {
        if (cancelled) return
        setSnapshot(null)
        const message =
          nextError instanceof Error
            ? nextError.message
            : "Failed to load companion workspace."
        setError(message)
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [capabilities?.hasPersonalization, capsLoading, isOnline, reloadToken])

  const handleRefresh = () => {
    setReloadToken((current) => current + 1)
  }

  const handleEnableCompanion = async () => {
    setEnablingCompanion(true)
    setError(null)
    try {
      const nextProfile = await updatePersonalizationOptIn(true)
      setProfile(nextProfile)
      onCompanionEnabled?.()
      handleRefresh()
    } catch (nextError) {
      setError(
        nextError instanceof Error
          ? nextError.message
          : "Failed to enable companion."
      )
    } finally {
      setEnablingCompanion(false)
    }
  }

  const handlePreferenceToggle = async (
    key: CompanionPreferenceToggleKey,
    value: boolean
  ) => {
    setSavingPreferenceKey(key)
    setError(null)
    try {
      const nextProfile = await updateCompanionPreferences({ [key]: value })
      setProfile(nextProfile)
    } catch (nextError) {
      setError(
        nextError instanceof Error
          ? nextError.message
          : "Failed to update companion settings."
      )
    } finally {
      setSavingPreferenceKey(null)
    }
  }

  const handleOpenKnowledgeProvenance = async (cardId: string) => {
    setLoadingProvenanceId(cardId)
    setError(null)
    try {
      const detail = await fetchCompanionKnowledgeDetail(cardId)
      setProvenance({ kind: "knowledge", detail })
    } catch (nextError) {
      setError(
        nextError instanceof Error
          ? nextError.message
          : "Failed to load knowledge provenance."
      )
    } finally {
      setLoadingProvenanceId(null)
    }
  }

  const handleOpenReflectionProvenance = async (reflectionId: string) => {
    setLoadingProvenanceId(reflectionId)
    setError(null)
    try {
      const detail = await fetchCompanionReflectionDetail(reflectionId)
      setProvenance({ kind: "reflection", detail })
    } catch (nextError) {
      setError(
        nextError instanceof Error
          ? nextError.message
          : "Failed to load reflection provenance."
      )
    } finally {
      setLoadingProvenanceId(null)
    }
  }

  const handleLifecycleRequest = (
    mode: "purge" | "rebuild",
    scope: CompanionLifecycleScope
  ) => {
    setPendingLifecycleAction({ mode, scope })
    setLifecycleResult(null)
    setError(null)
  }

  const handleConfirmLifecycleAction = async () => {
    if (!pendingLifecycleAction) return
    const actionKey = `${pendingLifecycleAction.mode}:${pendingLifecycleAction.scope}`
    setRunningLifecycleAction(actionKey)
    setError(null)
    try {
      const result =
        pendingLifecycleAction.mode === "purge"
          ? await purgeCompanionScope(pendingLifecycleAction.scope)
          : await queueCompanionRebuild(pendingLifecycleAction.scope)
      setLifecycleResult(result)
      setPendingLifecycleAction(null)
      if (pendingLifecycleAction.mode === "purge") {
        setProvenance(null)
        handleRefresh()
      }
    } catch (nextError) {
      setError(
        nextError instanceof Error
          ? nextError.message
          : "Failed to update companion lifecycle state."
      )
    } finally {
      setRunningLifecycleAction(null)
    }
  }

  const handleCreateGoal = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const trimmedTitle = goalForm.title.trim()
    const trimmedDescription = goalForm.description.trim()
    if (!trimmedTitle) return

    setCreatingGoal(true)
    setError(null)
    try {
      await createCompanionGoal({
        title: trimmedTitle,
        description: trimmedDescription || undefined,
        goal_type: "manual"
      })
      setGoalForm({ title: "", description: "" })
      handleRefresh()
    } catch (nextError) {
      setError(
        nextError instanceof Error
          ? nextError.message
          : "Failed to create companion goal."
      )
    } finally {
      setCreatingGoal(false)
    }
  }

  const handleGoalStatus = async (goalId: string, status: string) => {
    setUpdatingGoalId(goalId)
    setError(null)
    try {
      await setCompanionGoalStatus(goalId, status)
      handleRefresh()
    } catch (nextError) {
      setError(
        nextError instanceof Error
          ? nextError.message
          : "Failed to update companion goal."
      )
    } finally {
      setUpdatingGoalId(null)
    }
  }

  const handleCreateCheckIn = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const trimmedTitle = checkInForm.title.trim()
    const trimmedSummary = checkInForm.summary.trim()
    if (!trimmedSummary) return

    setSavingCheckIn(true)
    setError(null)
    try {
      await recordCompanionCheckIn({
        title: trimmedTitle || undefined,
        summary: trimmedSummary,
        tags: parseTagInput(checkInForm.tags)
      })
      setCheckInForm({ title: "", summary: "", tags: "" })
      handleRefresh()
    } catch (nextError) {
      setError(
        nextError instanceof Error
          ? nextError.message
          : "Failed to save companion check-in."
      )
    } finally {
      setSavingCheckIn(false)
    }
  }

  if (!isOnline) {
    return (
      <section className="mx-auto max-w-5xl px-6 py-10" data-testid="companion-offline">
        <h1 className="text-3xl font-semibold text-slate-900">Companion unavailable</h1>
        <p className="mt-3 max-w-2xl text-sm text-slate-600">
          Connect to your server to review explicit activity, derived knowledge, and
          companion reflections.
        </p>
      </section>
    )
  }

  if (capsLoading || loading) {
    return (
      <section className="mx-auto max-w-5xl px-6 py-10" data-testid="companion-loading">
        <h1 className="text-3xl font-semibold text-slate-900">Companion</h1>
        <p className="mt-3 text-sm text-slate-600">Loading your explicit-capture workspace.</p>
      </section>
    )
  }

  if (!capabilities?.hasPersonalization) {
    return (
      <section
        className="mx-auto max-w-5xl px-6 py-10"
        data-testid="companion-unavailable"
      >
        <h1 className="text-3xl font-semibold text-slate-900">Companion unavailable</h1>
        <p className="mt-3 max-w-2xl text-sm text-slate-600">
          This workspace depends on the personalization module. Enable that backend
          feature to view activity, knowledge cards, goals, and reflections here.
        </p>
      </section>
    )
  }

  if (!profile?.enabled) {
    return (
      <section
        className="mx-auto max-w-4xl px-6 py-10"
        data-testid="companion-consent-required"
      >
        <div className="rounded-3xl border border-amber-200 bg-gradient-to-br from-amber-50 via-white to-orange-50 p-8 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-amber-700">
            Explicit consent required
          </p>
          <h1 className="mt-3 text-3xl font-semibold text-slate-950">
            {t("option:header.companion", "Companion")}
          </h1>
          <p className="mt-4 text-base font-medium text-slate-900">
            Enable personalization before using Companion.
          </p>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
            Companion stores explicit captures, manual check-ins, and derived
            knowledge in your personalization profile only after you turn it on.
            Until then, this workspace stays read-only and extension saves should
            not persist anything.
          </p>
          {error ? (
            <div className="mt-5 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
              {error}
            </div>
          ) : null}
          <div className="mt-6 flex flex-wrap gap-3">
            <button
              className="rounded-full border border-slate-900 bg-slate-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={enablingCompanion}
              onClick={handleEnableCompanion}
              type="button"
            >
              {enablingCompanion ? "Enabling..." : "Enable Companion"}
            </button>
          </div>
        </div>
      </section>
    )
  }

  const activity = snapshot?.activity ?? []
  const knowledge = snapshot?.knowledge ?? []
  const goals = snapshot?.goals ?? []
  const reflections = snapshot?.reflections ?? []
  const showAdjacentLinks = surface === "options"
  const showLifecycleControls = surface === "options"

  return (
    <section className="mx-auto max-w-7xl px-6 py-8" data-testid="companion-page">
      <div className="rounded-3xl border border-slate-200 bg-gradient-to-br from-amber-50 via-white to-sky-50 p-6 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
              Explicit capture workspace
            </p>
            <h1 className="mt-2 text-3xl font-semibold text-slate-950">
              {t("option:header.companion", "Companion")}
            </h1>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              Review the activity you captured on purpose, the knowledge derived from
              it, the goals you are tracking, and the reflections the companion has
              already sent into your inbox.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              className="rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:border-slate-400"
              onClick={handleRefresh}
              type="button"
            >
              Refresh
            </button>
            {showAdjacentLinks ? (
              <Link
                className="rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:border-slate-400"
                to="/collections"
              >
                Open collections
              </Link>
            ) : null}
            {showAdjacentLinks ? (
              <Link
                className="rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:border-slate-400"
                to="/watchlists"
              >
                Open watchlists
              </Link>
            ) : null}
            {capabilities?.hasPersona ? (
              <Link
                className="rounded-full border border-slate-900 bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
                to="/companion/conversation"
              >
                Open conversation
              </Link>
            ) : null}
          </div>
        </div>

        <div className="mt-6 grid gap-3 md:grid-cols-4">
          <div className="rounded-2xl border border-white/70 bg-white/80 p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Activity
            </p>
            <p className="mt-2 text-2xl font-semibold text-slate-950">
              {snapshot?.activityTotal ?? 0}
            </p>
            <p className="mt-1 text-sm text-slate-600">Explicit events available to review.</p>
          </div>
          <div className="rounded-2xl border border-white/70 bg-white/80 p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Knowledge
            </p>
            <p className="mt-2 text-2xl font-semibold text-slate-950">
              {snapshot?.knowledgeTotal ?? 0}
            </p>
            <p className="mt-1 text-sm text-slate-600">Derived cards grounded in evidence.</p>
          </div>
          <div className="rounded-2xl border border-white/70 bg-white/80 p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Active goals
            </p>
            <p className="mt-2 text-2xl font-semibold text-slate-950">
              {snapshot?.activeGoalCount ?? 0}
            </p>
            <p className="mt-1 text-sm text-slate-600">Manual or activity-backed goals.</p>
          </div>
          <div className="rounded-2xl border border-white/70 bg-white/80 p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Reflections
            </p>
            <p className="mt-2 text-2xl font-semibold text-slate-950">
              {reflections.length}
            </p>
            <p className="mt-1 text-sm text-slate-600">
              {snapshot?.reflectionNotifications.length ?? 0} also visible in the inbox.
            </p>
          </div>
        </div>
      </div>

      {error ? (
        <div className="mt-6 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      ) : null}

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-6">
          <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold text-slate-950">Recent activity</h2>
                <p className="mt-1 text-sm text-slate-600">
                  Timeline entries stay anchored to explicit captures and actions.
                </p>
              </div>
            </div>
            <div className="mt-5 space-y-4">
              {activity.length ? (
                activity.map((item) => (
                  <article
                    className="rounded-2xl border border-slate-200 bg-slate-50 p-4"
                    key={item.id}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <h3 className="text-sm font-semibold text-slate-900">
                          {describeActivity(item)}
                        </h3>
                        <p className="mt-1 text-xs uppercase tracking-wide text-slate-500">
                          {titleCase(item.event_type)} · {item.surface}
                        </p>
                      </div>
                      <p className="text-xs text-slate-500">
                        {formatTimestamp(item.created_at)}
                      </p>
                    </div>
                    <p className="mt-3 text-sm text-slate-600">
                      Source: {item.source_type} #{item.source_id}
                    </p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {item.tags.map((tag) => (
                        <span
                          className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-slate-600"
                          key={`${item.id}:${tag}`}
                        >
                          {tag}
                        </span>
                      ))}
                      {typeof item.provenance.capture_mode === "string" ? (
                        <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-medium text-amber-800">
                          {String(item.provenance.capture_mode)}
                        </span>
                      ) : null}
                    </div>
                  </article>
                ))
              ) : (
                <p className="rounded-2xl border border-dashed border-slate-300 px-4 py-6 text-sm text-slate-500">
                  No activity yet. Save reading items, update notes, or complete reminder
                  work to start building the ledger.
                </p>
              )}
            </div>
          </section>

          <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-xl font-semibold text-slate-950">Knowledge cards</h2>
            <p className="mt-1 text-sm text-slate-600">
              These cards summarize themes the companion can defend with evidence.
            </p>
            <div className="mt-5 grid gap-4 md:grid-cols-2">
              {knowledge.length ? (
                knowledge.map((card) => (
                  <article
                    className="rounded-2xl border border-slate-200 bg-slate-50 p-4"
                    key={card.id}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <h3 className="text-sm font-semibold text-slate-900">{card.title}</h3>
                        <p className="mt-1 text-xs uppercase tracking-wide text-slate-500">
                          {titleCase(card.card_type)}
                        </p>
                      </div>
                      <span className="rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-medium text-emerald-800">
                        {card.status}
                      </span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-600">{card.summary}</p>
                    <p className="mt-3 text-xs text-slate-500">
                      Evidence: {card.evidence.length} · Updated {formatTimestamp(card.updated_at)}
                    </p>
                    <div className="mt-4">
                      <button
                        className="rounded-full border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:border-slate-400 disabled:cursor-not-allowed disabled:opacity-60"
                        disabled={loadingProvenanceId === card.id}
                        onClick={() => handleOpenKnowledgeProvenance(card.id)}
                        type="button"
                      >
                        View knowledge provenance
                      </button>
                    </div>
                  </article>
                ))
              ) : (
                <p className="rounded-2xl border border-dashed border-slate-300 px-4 py-6 text-sm text-slate-500">
                  Knowledge cards will appear here after enough explicit activity is
                  available to derive stable themes.
                </p>
              )}
            </div>
          </section>
        </div>

        <div className="space-y-6">
          <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-xl font-semibold text-slate-950">Settings</h2>
            <p className="mt-1 text-sm text-slate-600">
              Decide whether companion reflections are active before anything is
              queued or surfaced back to you.
            </p>
            <div className="mt-5 space-y-3">
              <label className="flex items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                <div>
                  <p className="text-sm font-medium text-slate-900">Companion reflections</p>
                  <p className="mt-1 text-xs text-slate-500">
                    Master switch for daily and weekly companion reflection jobs.
                  </p>
                </div>
                <input
                  aria-label="Companion reflections"
                  checked={profile?.companion_reflections_enabled !== false}
                  disabled={savingPreferenceKey === "companion_reflections_enabled"}
                  onChange={(event) =>
                    handlePreferenceToggle(
                      "companion_reflections_enabled",
                      event.target.checked
                    )
                  }
                  type="checkbox"
                />
              </label>
              <label className="flex items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                <div>
                  <p className="text-sm font-medium text-slate-900">Daily reflections</p>
                  <p className="mt-1 text-xs text-slate-500">
                    Allow the daily reflection cadence to enqueue when activity is present.
                  </p>
                </div>
                <input
                  aria-label="Daily reflections"
                  checked={profile?.companion_daily_reflections_enabled !== false}
                  disabled={
                    profile?.companion_reflections_enabled === false ||
                    savingPreferenceKey === "companion_daily_reflections_enabled"
                  }
                  onChange={(event) =>
                    handlePreferenceToggle(
                      "companion_daily_reflections_enabled",
                      event.target.checked
                    )
                  }
                  type="checkbox"
                />
              </label>
              <label className="flex items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                <div>
                  <p className="text-sm font-medium text-slate-900">Weekly reflections</p>
                  <p className="mt-1 text-xs text-slate-500">
                    Keep the weekly synthesis available for longer-running focus shifts.
                  </p>
                </div>
                <input
                  aria-label="Weekly reflections"
                  checked={profile?.companion_weekly_reflections_enabled !== false}
                  disabled={
                    profile?.companion_reflections_enabled === false ||
                    savingPreferenceKey === "companion_weekly_reflections_enabled"
                  }
                  onChange={(event) =>
                    handlePreferenceToggle(
                      "companion_weekly_reflections_enabled",
                      event.target.checked
                    )
                  }
                  type="checkbox"
                />
              </label>
              <label className="flex items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                <div>
                  <p className="text-sm font-medium text-slate-900">Proactive delivery</p>
                  <p className="mt-1 text-xs text-slate-500">
                    Control whether companion reflections can be delivered into the inbox.
                  </p>
                </div>
                <input
                  aria-label="Proactive delivery"
                  checked={profile?.proactive_enabled !== false}
                  disabled={savingPreferenceKey === "proactive_enabled"}
                  onChange={(event) =>
                    handlePreferenceToggle("proactive_enabled", event.target.checked)
                  }
                  type="checkbox"
                />
              </label>
            </div>
          </section>

          <section
            className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm"
            data-testid="companion-provenance"
          >
            <h2 className="text-xl font-semibold text-slate-950">Provenance</h2>
            <p className="mt-1 text-sm text-slate-600">
              Inspect the exact ids and resolved records behind a knowledge card or reflection.
            </p>
            <div className="mt-5">
              {!provenance ? (
                <p className="rounded-2xl border border-dashed border-slate-300 px-4 py-6 text-sm text-slate-500">
                  Choose “View provenance” on a knowledge card or reflection to inspect its
                  source event ids, linked cards, and goals.
                </p>
              ) : provenance.kind === "reflection" ? (
                <div className="space-y-4">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Reflection detail
                    </p>
                    <h3 className="mt-1 text-base font-semibold text-slate-950">
                      {provenance.detail.title}
                    </h3>
                    <p className="mt-2 text-sm leading-6 text-slate-600">
                      {provenance.detail.summary}
                    </p>
                  </div>
                  {normalizeFollowUpPrompts(provenance.detail.follow_up_prompts).length ? (
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Follow-up prompts
                      </p>
                      <p className="mt-1 text-sm text-slate-600">
                        These stay visible only after you open a reflection detail.
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {normalizeFollowUpPrompts(provenance.detail.follow_up_prompts).map(
                          (prompt) => (
                            <button
                              className="rounded-full border border-sky-200 bg-sky-50 px-3 py-1.5 text-sm font-medium text-sky-800"
                              key={prompt.prompt_id}
                              type="button"
                            >
                              {prompt.label}
                            </button>
                          )
                        )}
                      </div>
                    </div>
                  ) : null}
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Source event ids
                    </p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {(Array.isArray(provenance.detail.provenance.source_event_ids)
                        ? provenance.detail.provenance.source_event_ids
                        : []
                      ).map((item) => (
                        <span
                          className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700"
                          key={String(item)}
                        >
                          {String(item)}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="grid gap-3 md:grid-cols-2">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Knowledge cards
                      </p>
                      <div className="mt-2 space-y-2">
                        {provenance.detail.knowledge_cards.map((card) => (
                          <div
                            className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700"
                            key={card.id}
                          >
                            <span className="font-medium">{card.id}</span>
                            <div className="mt-1 text-xs text-slate-500">{card.title}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Goals
                      </p>
                      <div className="mt-2 space-y-2">
                        {provenance.detail.goals.map((goal) => (
                          <div
                            className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700"
                            key={goal.id}
                          >
                            <span className="font-medium">{goal.id}</span>
                            <div className="mt-1 text-xs text-slate-500">{goal.title}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Knowledge detail
                    </p>
                    <h3 className="mt-1 text-base font-semibold text-slate-950">
                      {provenance.detail.title}
                    </h3>
                    <p className="mt-2 text-sm leading-6 text-slate-600">
                      {provenance.detail.summary}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Source event ids
                    </p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {provenance.detail.evidence_events.map((item) => (
                        <span
                          className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700"
                          key={item.id}
                        >
                          {item.id}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="grid gap-3 md:grid-cols-2">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Evidence events
                      </p>
                      <div className="mt-2 space-y-2">
                        {provenance.detail.evidence_events.map((item) => (
                          <div
                            className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700"
                            key={item.id}
                          >
                            <span className="font-medium">{item.id}</span>
                            <div className="mt-1 text-xs text-slate-500">
                              {describeActivity(item)}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Evidence goals
                      </p>
                      <div className="mt-2 space-y-2">
                        {provenance.detail.evidence_goals.map((goal) => (
                          <div
                            className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700"
                            key={goal.id}
                          >
                            <span className="font-medium">{goal.id}</span>
                            <div className="mt-1 text-xs text-slate-500">{goal.title}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </section>

          {showLifecycleControls ? (
            <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold text-slate-950">Lifecycle controls</h2>
              <p className="mt-1 text-sm text-slate-600">
                Purge or rebuild only derived companion state. Explicit activity remains intact.
              </p>
              <div className="mt-5 grid gap-3">
                {(["knowledge", "reflections", "derived_goals", "goal_progress"] as CompanionLifecycleScope[]).map((scope) => (
                  <div
                    className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3"
                    key={scope}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-medium text-slate-900">
                          {titleCase(lifecycleScopeLabel(scope))}
                        </p>
                        <p className="mt-1 text-xs text-slate-500">
                          Scoped action only for {lifecycleScopeLabel(scope)}.
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <button
                          className="rounded-full border border-rose-300 bg-rose-50 px-3 py-1.5 text-sm font-medium text-rose-700 hover:border-rose-400 disabled:cursor-not-allowed disabled:opacity-60"
                          disabled={runningLifecycleAction !== null}
                          onClick={() => handleLifecycleRequest("purge", scope)}
                          type="button"
                        >
                          {`Purge ${lifecycleScopeLabel(scope)}`}
                        </button>
                        <button
                          className="rounded-full border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:border-slate-400 disabled:cursor-not-allowed disabled:opacity-60"
                          disabled={runningLifecycleAction !== null}
                          onClick={() => handleLifecycleRequest("rebuild", scope)}
                          type="button"
                        >
                          {`Rebuild ${lifecycleScopeLabel(scope)}`}
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              {pendingLifecycleAction ? (
                <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3">
                  <p className="text-sm font-medium text-amber-900">
                    Confirm {pendingLifecycleAction.mode} for{" "}
                    {lifecycleScopeLabel(pendingLifecycleAction.scope)}?
                  </p>
                  <p className="mt-1 text-xs text-amber-800">
                    This only affects derived companion data. Explicit captured activity stays intact.
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button
                      className="rounded-full border border-amber-900 bg-amber-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-800 disabled:cursor-not-allowed disabled:opacity-60"
                      disabled={runningLifecycleAction !== null}
                      onClick={handleConfirmLifecycleAction}
                      type="button"
                    >
                      {`Confirm ${pendingLifecycleAction.mode} ${lifecycleScopeLabel(
                        pendingLifecycleAction.scope
                      )}`}
                    </button>
                    <button
                      className="rounded-full border border-amber-300 bg-white px-3 py-1.5 text-sm font-medium text-amber-800 hover:border-amber-400"
                      onClick={() => setPendingLifecycleAction(null)}
                      type="button"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : null}
              {lifecycleResult ? (
                <div className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
                  {lifecycleResult.status === "queued"
                    ? `Rebuild queued for ${lifecycleScopeLabel(lifecycleResult.scope)}${lifecycleResult.job_id ? ` (job #${lifecycleResult.job_id})` : ""}.`
                    : `${titleCase(lifecycleResult.status)} ${lifecycleScopeLabel(
                        lifecycleResult.scope
                      )}.`}
                </div>
              ) : null}
            </section>
          ) : null}

          <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <div>
              <h2 className="text-xl font-semibold text-slate-950">Manual check-in</h2>
              <p className="mt-1 text-sm text-slate-600">
                Capture an intentional update in your own words so the companion has a
                durable, explicit state change to reference later.
              </p>
            </div>

            <form className="mt-5 space-y-3" onSubmit={handleCreateCheckIn}>
              <div>
                <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">
                  Check-in title
                </label>
                <input
                  aria-label="Check-in title"
                  className="w-full rounded-2xl border border-slate-300 px-3 py-2 text-sm text-slate-900 outline-none ring-0 placeholder:text-slate-400 focus:border-slate-500"
                  onChange={(event) =>
                    updateCheckInForm("title", event.target.value)
                  }
                  placeholder="Morning reset"
                  value={checkInForm.title}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">
                  Summary
                </label>
                <textarea
                  aria-label="Summary"
                  className="min-h-[100px] w-full rounded-2xl border border-slate-300 px-3 py-2 text-sm text-slate-900 outline-none ring-0 placeholder:text-slate-400 focus:border-slate-500"
                  onChange={(event) =>
                    updateCheckInForm("summary", event.target.value)
                  }
                  placeholder="Re-focused on the companion capture backlog before lunch."
                  value={checkInForm.summary}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">
                  Tags
                </label>
                <input
                  aria-label="Tags"
                  className="w-full rounded-2xl border border-slate-300 px-3 py-2 text-sm text-slate-900 outline-none ring-0 placeholder:text-slate-400 focus:border-slate-500"
                  onChange={(event) =>
                    updateCheckInForm("tags", event.target.value)
                  }
                  placeholder="planning, focus"
                  value={checkInForm.tags}
                />
              </div>
              <button
                className="rounded-full border border-slate-900 bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:border-slate-300 disabled:bg-slate-300"
                disabled={savingCheckIn || !checkInForm.summary.trim()}
                type="submit"
              >
                {savingCheckIn ? "Saving..." : "Save check-in"}
              </button>
            </form>
          </section>

          <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold text-slate-950">Goals</h2>
                <p className="mt-1 text-sm text-slate-600">
                  Track intent explicitly and let companion summaries show progress.
                </p>
              </div>
            </div>

            <form className="mt-5 space-y-3" onSubmit={handleCreateGoal}>
              <div>
                <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">
                  Goal title
                </label>
                <input
                  className="w-full rounded-2xl border border-slate-300 px-3 py-2 text-sm text-slate-900 outline-none ring-0 placeholder:text-slate-400 focus:border-slate-500"
                  onChange={(event) => updateGoalForm("title", event.target.value)}
                  placeholder="Capture a weekly review"
                  value={goalForm.title}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">
                  Description
                </label>
                <textarea
                  className="min-h-[88px] w-full rounded-2xl border border-slate-300 px-3 py-2 text-sm text-slate-900 outline-none ring-0 placeholder:text-slate-400 focus:border-slate-500"
                  onChange={(event) =>
                    updateGoalForm("description", event.target.value)
                  }
                  placeholder="Keep the explicit companion loop active every Friday."
                  value={goalForm.description}
                />
              </div>
              <button
                className="rounded-full border border-slate-900 bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:border-slate-300 disabled:bg-slate-300"
                disabled={creatingGoal || !goalForm.title.trim()}
                type="submit"
              >
                {creatingGoal ? "Creating..." : "Create goal"}
              </button>
            </form>

            <div className="mt-5 space-y-4">
              {goals.length ? (
                goals.map((goal) => {
                  const isUpdating = updatingGoalId === goal.id
                  const nextStatus = goal.status === "active" ? "paused" : "active"
                  const nextLabel = goal.status === "active" ? "Pause" : "Resume"
                  return (
                    <article
                      className="rounded-2xl border border-slate-200 bg-slate-50 p-4"
                      key={goal.id}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <h3 className="text-sm font-semibold text-slate-900">
                            {goal.title}
                          </h3>
                          <p className="mt-1 text-xs uppercase tracking-wide text-slate-500">
                            {titleCase(goal.goal_type)}
                          </p>
                        </div>
                        <span className="rounded-full bg-sky-100 px-2.5 py-1 text-xs font-medium text-sky-800">
                          {goal.status}
                        </span>
                      </div>
                      {goal.description ? (
                        <p className="mt-3 text-sm leading-6 text-slate-600">
                          {goal.description}
                        </p>
                      ) : null}
                      <p className="mt-3 text-xs text-slate-500">{summarizeProgress(goal)}</p>
                      <div className="mt-4 flex flex-wrap gap-3">
                        <button
                          className="rounded-full border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:border-slate-400 disabled:cursor-not-allowed disabled:opacity-60"
                          disabled={isUpdating}
                          onClick={() => handleGoalStatus(goal.id, nextStatus)}
                          type="button"
                        >
                          {nextLabel}
                        </button>
                        {goal.status !== "completed" ? (
                          <button
                            className="rounded-full border border-emerald-300 bg-emerald-50 px-3 py-1.5 text-sm font-medium text-emerald-700 hover:border-emerald-400 disabled:cursor-not-allowed disabled:opacity-60"
                            disabled={isUpdating}
                            onClick={() => handleGoalStatus(goal.id, "completed")}
                            type="button"
                          >
                            Complete
                          </button>
                        ) : null}
                      </div>
                    </article>
                  )
                })
              ) : (
                <p className="rounded-2xl border border-dashed border-slate-300 px-4 py-6 text-sm text-slate-500">
                  No goals yet. Create one here or let future companion workflows propose
                  them from your explicit activity patterns.
                </p>
              )}
            </div>
          </section>

          <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-xl font-semibold text-slate-950">Reflections</h2>
            <p className="mt-1 text-sm text-slate-600">
              Daily and weekly outputs stay inspectable with provenance and inbox linkage.
            </p>
            <div className="mt-5 space-y-4">
              {reflections.length ? (
                reflections.map((reflection) => {
                  const inboxLabel = snapshot
                    ? reflectionInboxLabel(reflection, snapshot)
                    : null
                  return (
                    <article
                      className="rounded-2xl border border-slate-200 bg-slate-50 p-4"
                      key={reflection.id}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <h3 className="text-sm font-semibold text-slate-900">
                            {reflection.title || "Companion reflection"}
                          </h3>
                          <p className="mt-1 text-xs uppercase tracking-wide text-slate-500">
                            {reflection.cadence ? `${reflection.cadence} cadence` : "Derived reflection"}
                          </p>
                        </div>
                        <p className="text-xs text-slate-500">
                          {formatTimestamp(reflection.created_at)}
                        </p>
                      </div>
                      <p className="mt-3 text-sm leading-6 text-slate-600">
                        {reflection.summary}
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <span className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-slate-600">
                          Evidence: {reflection.evidence.length}
                        </span>
                        {inboxLabel ? (
                          <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-medium text-amber-800">
                            {inboxLabel}
                          </span>
                        ) : null}
                      </div>
                      <div className="mt-4">
                        <button
                          className="rounded-full border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:border-slate-400 disabled:cursor-not-allowed disabled:opacity-60"
                          disabled={loadingProvenanceId === reflection.id}
                          onClick={() => handleOpenReflectionProvenance(reflection.id)}
                          type="button"
                        >
                          View reflection provenance
                        </button>
                      </div>
                    </article>
                  )
                })
              ) : (
                <p className="rounded-2xl border border-dashed border-slate-300 px-4 py-6 text-sm text-slate-500">
                  Reflections will appear here after the Jobs-backed companion cadence has
                  enough activity to summarize.
                </p>
              )}
            </div>
          </section>
        </div>
      </div>
    </section>
  )
}

export default CompanionPage
