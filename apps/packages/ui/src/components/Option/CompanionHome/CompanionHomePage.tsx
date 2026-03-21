import React from "react"
import { Link } from "react-router-dom"

import { useServerCapabilities } from "@/hooks/useServerCapabilities"
import {
  fetchPersonalizationProfile,
  type PersonalizationProfile,
  updatePersonalizationOptIn
} from "@/services/companion"
import {
  fetchCompanionHomeSnapshot,
  type CompanionHomeSnapshot,
  type CompanionHomeSurface
} from "@/services/companion-home"
import {
  DEFAULT_COMPANION_HOME_LAYOUT,
  loadCompanionHomeLayout,
  saveCompanionHomeLayout,
  type CompanionHomeLayoutCard
} from "@/store/companion-home-layout"

import { CustomizeHomeDrawer } from "./CustomizeHomeDrawer"
import { GoalsFocusCard } from "./cards/GoalsFocusCard"
import { InboxPreviewCard } from "./cards/InboxPreviewCard"
import { NeedsAttentionCard } from "./cards/NeedsAttentionCard"
import { ReadingQueueCard } from "./cards/ReadingQueueCard"
import { RecentActivityCard } from "./cards/RecentActivityCard"
import { ResumeWorkCard } from "./cards/ResumeWorkCard"
import type { CompanionHomeCardState } from "./cards/CardShell"

type CompanionHomePageProps = {
  surface: CompanionHomeSurface
}

const createEmptySnapshot = (
  surface: CompanionHomeSurface
): CompanionHomeSnapshot => ({
  surface,
  inbox: [],
  needsAttention: [],
  resumeWork: [],
  goalsFocus: [],
  recentActivity: [],
  readingQueue: [],
  degradedSources: ["workspace", "reading", "notes"],
  summary: {
    activityCount: 0,
    inboxCount: 0,
    needsAttentionCount: 0,
    resumeWorkCount: 0
  }
})

const formatDegradedSources = (sources: CompanionHomeSnapshot["degradedSources"]): string =>
  sources
    .map((source) => {
      if (source === "workspace") return "companion workspace"
      if (source === "reading") return "reading queue"
      return "notes"
    })
    .join(", ")

export function CompanionHomePage({ surface }: CompanionHomePageProps) {
  const { capabilities, loading: capsLoading } = useServerCapabilities()
  const [snapshot, setSnapshot] = React.useState<CompanionHomeSnapshot | null>(null)
  const [layout, setLayout] = React.useState<CompanionHomeLayoutCard[] | null>(null)
  const [profile, setProfile] = React.useState<PersonalizationProfile | null>(null)
  const [profileLoaded, setProfileLoaded] = React.useState(false)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const [enablingCompanion, setEnablingCompanion] = React.useState(false)
  const [refreshToken, setRefreshToken] = React.useState(0)
  const [customizeOpen, setCustomizeOpen] = React.useState(false)
  const layoutLoadRequestRef = React.useRef(0)
  const layoutMutationVersionRef = React.useRef(0)

  const hasPersonalization = Boolean(capabilities?.hasPersonalization)
  const hasConversationRoute =
    Boolean(capabilities?.hasPersonalization) &&
    Boolean(capabilities?.hasPersona) &&
    profileLoaded &&
    Boolean(profile?.enabled)

  React.useEffect(() => {
    let cancelled = false
    const requestId = layoutLoadRequestRef.current + 1
    const mutationVersionAtRequest = layoutMutationVersionRef.current

    layoutLoadRequestRef.current = requestId
    setLayout(null)

    const loadLayout = async () => {
      try {
        const nextLayout = await loadCompanionHomeLayout(surface)
        if (
          !cancelled &&
          layoutLoadRequestRef.current === requestId &&
          layoutMutationVersionRef.current === mutationVersionAtRequest
        ) {
          setLayout(nextLayout)
        }
      } catch {
        if (
          !cancelled &&
          layoutLoadRequestRef.current === requestId &&
          layoutMutationVersionRef.current === mutationVersionAtRequest
        ) {
          setLayout(DEFAULT_COMPANION_HOME_LAYOUT)
        }
      }
    }

    void loadLayout()

    return () => {
      cancelled = true
    }
  }, [surface])

  React.useEffect(() => {
    if (capsLoading) return

    let cancelled = false
    setLoading(true)
    setError(null)
    setProfileLoaded(false)

    const load = async () => {
      const [snapshotResult, profileResult] = await Promise.allSettled([
        fetchCompanionHomeSnapshot(surface),
        hasPersonalization ? fetchPersonalizationProfile() : Promise.resolve(null)
      ])

      if (cancelled) {
        return
      }

      if (snapshotResult.status === "fulfilled") {
        setSnapshot(snapshotResult.value)
      } else {
        setSnapshot(createEmptySnapshot(surface))
        setError("Companion Home is partially unavailable right now.")
      }

      if (profileResult.status === "fulfilled") {
        setProfile(profileResult.value)
        setProfileLoaded(true)
      } else {
        setProfile(null)
        setError((current) => current || "Companion setup status could not be loaded.")
      }

      setLoading(false)
    }

    void load()

    return () => {
      cancelled = true
    }
  }, [capsLoading, hasPersonalization, refreshToken, surface])

  const refresh = React.useCallback(() => {
    setRefreshToken((value) => value + 1)
  }, [])

  const handleLayoutChange = React.useCallback(
    (nextLayout: CompanionHomeLayoutCard[]) => {
      layoutMutationVersionRef.current += 1
      setLayout(nextLayout)
      void saveCompanionHomeLayout(surface, nextLayout)
    },
    [surface]
  )

  const handleEnableCompanion = React.useCallback(async () => {
    setEnablingCompanion(true)
    setError(null)
    try {
      const nextProfile = await updatePersonalizationOptIn(true)
      setProfile(nextProfile)
      refresh()
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Failed to enable companion personalization."
      )
    } finally {
      setEnablingCompanion(false)
    }
  }, [refresh])

  if (capsLoading || (loading && !snapshot)) {
    return (
      <div className="rounded-3xl border border-border/80 bg-surface/90 p-6 shadow-sm" data-testid="companion-home-page">
        <h1 className="text-3xl font-semibold text-text">Companion</h1>
        <p className="mt-3 text-sm text-text-muted">Loading your companion home dashboard.</p>
      </div>
    )
  }

  const resolvedSnapshot = snapshot ?? createEmptySnapshot(surface)
  const workspaceUnavailable = resolvedSnapshot.degradedSources.includes("workspace")
  const readingUnavailable = resolvedSnapshot.degradedSources.includes("reading")
  const notesUnavailable = resolvedSnapshot.degradedSources.includes("notes")

  const resolvePersonalizedCardState = (
    itemsLength: number,
    setupDescription: string,
    unavailableDescription: string
  ): CompanionHomeCardState | undefined => {
    if (itemsLength > 0) return undefined
    if (!hasPersonalization) {
      return {
        label: "Setup required",
        description: setupDescription
      }
    }
    if (profileLoaded && !profile?.enabled) {
      return {
        label: "Enable Companion",
        description: setupDescription
      }
    }
    if (workspaceUnavailable) {
      return {
        label: "Temporarily unavailable",
        description: unavailableDescription
      }
    }
    return undefined
  }

  const inboxState = resolvePersonalizedCardState(
    resolvedSnapshot.inbox.length,
    "Companion inbox items unlock once personalization is available for this workspace.",
    "Companion inbox data is temporarily unavailable."
  )

  const needsAttentionState =
    resolvedSnapshot.needsAttention.length > 0
      ? undefined
      : !hasPersonalization
        ? {
            label: "Setup required",
            description:
              "Companion setup unlocks needs-attention signals from goals and reading."
          }
        : profileLoaded && !profile?.enabled
          ? {
              label: "Enable Companion",
              description:
                "Enable Companion to surface needs-attention signals from goals and reading."
            }
          : workspaceUnavailable || readingUnavailable
            ? {
                label: "Temporarily unavailable",
                description:
                  "Needs-attention signals are limited until companion and reading sources come back."
              }
            : undefined

  const resumeWorkState =
    resolvedSnapshot.resumeWork.length > 0
      ? undefined
      : !hasPersonalization
        ? {
            label: "Setup required",
            description:
              "Companion setup unlocks resume suggestions across goals, reading, and notes."
          }
        : profileLoaded && !profile?.enabled
          ? {
              label: "Enable Companion",
              description:
                "Enable Companion to surface resume suggestions across goals, reading, and notes."
            }
          : workspaceUnavailable || readingUnavailable || notesUnavailable
            ? {
                label: "Temporarily unavailable",
                description:
                  "Resume suggestions are limited until companion, reading, and note sources are available."
              }
            : undefined

  const goalsState = resolvePersonalizedCardState(
    resolvedSnapshot.goalsFocus.length,
    "Enable Companion to turn goals and focus prompts into a live dashboard block.",
    "Goal focus data is temporarily unavailable."
  )

  const recentActivityState = resolvePersonalizedCardState(
    resolvedSnapshot.recentActivity.length,
    "Enable Companion to review recent activity and capture trails here.",
    "Recent activity is temporarily unavailable."
  )

  const readingState =
    resolvedSnapshot.readingQueue.length === 0 && readingUnavailable
      ? {
          label: "Temporarily unavailable",
          description: "Reading queue data is temporarily unavailable."
        }
      : undefined

  const topBand =
    !hasPersonalization
      ? {
          eyebrow: "Setup",
          title: "Companion setup required",
          description:
            "This server has not enabled personalization yet. The home hub stays available so you can still keep an eye on non-personalized work.",
          action: null
        }
      : profileLoaded && !profile?.enabled
        ? {
            eyebrow: "Setup",
            title: "Companion setup required",
            description:
              "Enable personalization to unlock goals, recent activity, and conversation from this home dashboard.",
            action: (
              <button
                className="rounded-full border border-text bg-text px-4 py-2 text-sm font-medium text-bg hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={enablingCompanion}
                onClick={handleEnableCompanion}
                type="button"
              >
                {enablingCompanion ? "Enabling..." : "Enable Companion"}
              </button>
            )
          }
        : resolvedSnapshot.degradedSources.length > 0
          ? {
              eyebrow: "Status",
              title: "Some companion modules are degraded",
              description: `Still showing available cards while ${formatDegradedSources(
                resolvedSnapshot.degradedSources
              )} reloads.`,
              action: null
            }
          : null

  const renderCoreCard = (cardId: CompanionHomeLayoutCard["id"]): React.ReactNode => {
    if (cardId === "resume-work") {
      return <ResumeWorkCard items={resolvedSnapshot.resumeWork} state={resumeWorkState} />
    }
    if (cardId === "goals-focus") {
      return <GoalsFocusCard items={resolvedSnapshot.goalsFocus} state={goalsState} />
    }
    if (cardId === "recent-activity") {
      return (
        <RecentActivityCard
          items={resolvedSnapshot.recentActivity}
          state={recentActivityState}
        />
      )
    }
    if (cardId === "reading-queue") {
      return <ReadingQueueCard items={resolvedSnapshot.readingQueue} state={readingState} />
    }
    return null
  }

  const orderedVisibleCoreCards = (layout ?? [])
    .filter((card) => card.kind === "core" && card.visible)
    .map((card) => ({
      id: card.id,
      node: renderCoreCard(card.id)
    }))
    .filter(
      (
        entry
      ): entry is {
        id: CompanionHomeLayoutCard["id"]
        node: React.ReactNode
      } => entry.node != null
    )

  return (
    <div className="flex flex-col gap-6" data-testid="companion-home-page">
      <header className="rounded-3xl border border-border/80 bg-[linear-gradient(135deg,rgba(255,248,235,0.96),rgba(245,248,255,0.92))] p-6 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
              Companion Home
            </p>
            <h1 className="mt-2 text-3xl font-semibold text-text">Companion</h1>
            <p className="mt-3 text-sm leading-6 text-text-muted">
              Review what is waiting in your inbox, what needs attention next, and which work threads are worth resuming right now.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              className="rounded-full border border-border bg-surface px-4 py-2 text-sm font-medium text-text transition-colors hover:border-primary/40 hover:bg-primary/5"
              onClick={() => setCustomizeOpen(true)}
              type="button"
            >
              Customize Home
            </button>
            <button
              className="rounded-full border border-border bg-surface px-4 py-2 text-sm font-medium text-text transition-colors hover:border-primary/40 hover:bg-primary/5"
              onClick={refresh}
              type="button"
            >
              Refresh
            </button>
            {hasConversationRoute ? (
              <Link
                className="rounded-full border border-text bg-text px-4 py-2 text-sm font-medium text-bg hover:opacity-90"
                to="/companion/conversation"
              >
                Open conversation
              </Link>
            ) : null}
          </div>
        </div>

        {topBand ? (
          <div className="mt-5 rounded-2xl border border-amber-300/70 bg-amber-50/80 px-4 py-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-amber-800">
              {topBand.eyebrow}
            </p>
            <div className="mt-2 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div className="max-w-3xl">
                <h2 className="text-xl font-semibold text-text">{topBand.title}</h2>
                <p className="mt-2 text-sm leading-6 text-text-muted">{topBand.description}</p>
              </div>
              {topBand.action}
            </div>
          </div>
        ) : null}

        <div
          className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4"
          data-testid="companion-home-summary"
        >
          {[
            {
              label: "Inbox",
              value: resolvedSnapshot.summary.inboxCount,
              description: "Unread or newly surfaced items"
            },
            {
              label: "Goals",
              value: resolvedSnapshot.goalsFocus.length,
              description: "Live priorities in focus"
            },
            {
              label: "Reading",
              value: resolvedSnapshot.readingQueue.length,
              description: "Queued items ready to revisit"
            },
            {
              label: "Resume",
              value: resolvedSnapshot.summary.resumeWorkCount,
              description: "Threads worth picking back up"
            }
          ].map((item) => (
            <div
              key={item.label}
              className="rounded-2xl border border-border/70 bg-surface/75 px-4 py-3 shadow-sm"
            >
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                {item.label}
              </p>
              <p className="mt-2 text-2xl font-semibold text-text">{item.value}</p>
              <p className="mt-1 text-sm text-text-muted">{item.description}</p>
            </div>
          ))}
        </div>

        {error ? (
          <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {error}
          </div>
        ) : null}
      </header>

      <div className="grid gap-4 xl:grid-cols-2">
        <InboxPreviewCard items={resolvedSnapshot.inbox} state={inboxState} />
        <NeedsAttentionCard
          items={resolvedSnapshot.needsAttention}
          state={needsAttentionState}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        {layout == null ? (
          <div
            className="rounded-3xl border border-dashed border-border/70 bg-bg/50 px-5 py-6 text-sm text-text-muted xl:col-span-2"
            data-testid="companion-home-core-layout-loading"
          >
            Loading your home layout.
          </div>
        ) : (
          orderedVisibleCoreCards.map((entry) => (
            <React.Fragment key={entry.id}>{entry.node}</React.Fragment>
          ))
        )}
      </div>

      <CustomizeHomeDrawer
        open={customizeOpen}
        layout={layout ?? DEFAULT_COMPANION_HOME_LAYOUT}
        onClose={() => setCustomizeOpen(false)}
        onLayoutChange={handleLayoutChange}
      />
    </div>
  )
}
