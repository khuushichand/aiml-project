import React from "react"
import { Link } from "react-router-dom"
import { useTranslation } from "react-i18next"

import { useServerCapabilities } from "@/hooks/useServerCapabilities"
import { useServerOnline } from "@/hooks/useServerOnline"
import {
  createCompanionGoal,
  fetchPersonalizationProfile,
  fetchCompanionWorkspaceSnapshot,
  recordCompanionCheckIn,
  setCompanionGoalStatus,
  type CompanionActivityItem,
  type CompanionGoal,
  type PersonalizationProfile,
  type CompanionReflection,
  type CompanionWorkspaceSnapshot,
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

type CompanionPageProps = {
  surface?: "options" | "sidepanel"
  onCompanionEnabled?: () => void
}

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
  const [checkInTitle, setCheckInTitle] = React.useState("")
  const [checkInSummary, setCheckInSummary] = React.useState("")
  const [checkInTags, setCheckInTags] = React.useState("")
  const [savingCheckIn, setSavingCheckIn] = React.useState(false)
  const [goalTitle, setGoalTitle] = React.useState("")
  const [goalDescription, setGoalDescription] = React.useState("")
  const [creatingGoal, setCreatingGoal] = React.useState(false)
  const [updatingGoalId, setUpdatingGoalId] = React.useState<string | null>(null)
  const [enablingCompanion, setEnablingCompanion] = React.useState(false)

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

  const handleCreateGoal = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const trimmedTitle = goalTitle.trim()
    const trimmedDescription = goalDescription.trim()
    if (!trimmedTitle) return

    setCreatingGoal(true)
    setError(null)
    try {
      await createCompanionGoal({
        title: trimmedTitle,
        description: trimmedDescription || undefined,
        goal_type: "manual"
      })
      setGoalTitle("")
      setGoalDescription("")
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
    const trimmedTitle = checkInTitle.trim()
    const trimmedSummary = checkInSummary.trim()
    if (!trimmedSummary) return

    setSavingCheckIn(true)
    setError(null)
    try {
      await recordCompanionCheckIn({
        title: trimmedTitle || undefined,
        summary: trimmedSummary,
        tags: parseTagInput(checkInTags)
      })
      setCheckInTitle("")
      setCheckInSummary("")
      setCheckInTags("")
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
                  onChange={(event) => setCheckInTitle(event.target.value)}
                  placeholder="Morning reset"
                  value={checkInTitle}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">
                  Summary
                </label>
                <textarea
                  aria-label="Summary"
                  className="min-h-[100px] w-full rounded-2xl border border-slate-300 px-3 py-2 text-sm text-slate-900 outline-none ring-0 placeholder:text-slate-400 focus:border-slate-500"
                  onChange={(event) => setCheckInSummary(event.target.value)}
                  placeholder="Re-focused on the companion capture backlog before lunch."
                  value={checkInSummary}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">
                  Tags
                </label>
                <input
                  aria-label="Tags"
                  className="w-full rounded-2xl border border-slate-300 px-3 py-2 text-sm text-slate-900 outline-none ring-0 placeholder:text-slate-400 focus:border-slate-500"
                  onChange={(event) => setCheckInTags(event.target.value)}
                  placeholder="planning, focus"
                  value={checkInTags}
                />
              </div>
              <button
                className="rounded-full border border-slate-900 bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:border-slate-300 disabled:bg-slate-300"
                disabled={savingCheckIn || !checkInSummary.trim()}
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
                  onChange={(event) => setGoalTitle(event.target.value)}
                  placeholder="Capture a weekly review"
                  value={goalTitle}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">
                  Description
                </label>
                <textarea
                  className="min-h-[88px] w-full rounded-2xl border border-slate-300 px-3 py-2 text-sm text-slate-900 outline-none ring-0 placeholder:text-slate-400 focus:border-slate-500"
                  onChange={(event) => setGoalDescription(event.target.value)}
                  placeholder="Keep the explicit companion loop active every Friday."
                  value={goalDescription}
                />
              </div>
              <button
                className="rounded-full border border-slate-900 bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:border-slate-300 disabled:bg-slate-300"
                disabled={creatingGoal || !goalTitle.trim()}
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
