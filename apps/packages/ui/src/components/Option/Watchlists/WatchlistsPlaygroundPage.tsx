import React, { useCallback, useEffect, useRef } from "react"
import { Alert, Button, Empty, Modal, Tabs } from "antd"
import { DismissibleBetaAlert } from "@/components/Common/DismissibleBetaAlert"
import type { TabsProps } from "antd"
import {
  CalendarClock,
  ExternalLink,
  FileOutput,
  FileText,
  LayoutDashboard,
  Newspaper,
  Play,
  Rss,
  Settings
} from "lucide-react"
import { useTranslation } from "react-i18next"
import { useAntdNotification } from "@/hooks/useAntdNotification"
import { useServerOnline } from "@/hooks/useServerOnline"
import { PageShell } from "@/components/Common/PageShell"
import { fetchWatchlistRuns } from "@/services/watchlists"
import { useWatchlistsStore } from "@/store/watchlists"
import type { WatchlistRun } from "@/types/watchlists"
import { OverviewTab } from "./OverviewTab/OverviewTab"
import { SourcesTab } from "./SourcesTab/SourcesTab"
import { JobsTab } from "./JobsTab/JobsTab"
import { RunsTab } from "./RunsTab/RunsTab"
import { OutputsTab } from "./OutputsTab/OutputsTab"
import { TemplatesTab } from "./TemplatesTab/TemplatesTab"
import { SettingsTab } from "./SettingsTab/SettingsTab"
import { ItemsTab } from "./ItemsTab/ItemsTab"
import {
  WATCHLISTS_ISSUE_REPORT_URL,
  WATCHLISTS_MAIN_DOCS_URL,
  WATCHLISTS_TAB_HELP_DOCS
} from "./shared/help-docs"
import {
  buildRunStateNotificationKey,
  dedupeRunNotificationEvents,
  groupRunNotificationEvents,
  getRunFailureHint,
  resolveStalledRunNotification,
  resolveRunTransitionNotification,
  shouldNotifyNewTerminalRun
} from "./RunsTab/run-notifications"
import { trackWatchlistsIaExperimentTransition } from "@/utils/watchlists-ia-experiment-telemetry"
import { trackWatchlistsOnboardingTelemetry } from "@/utils/watchlists-onboarding-telemetry"

const RUN_NOTIFICATIONS_POLL_MS = 15_000
const RUN_NOTIFICATIONS_PAGE_SIZE = 25
const RUN_NOTIFICATIONS_MIN_POLL_MS = 100
const RUN_STALLED_THRESHOLD_MS = 45 * 60_000
const GUIDED_TOUR_STORAGE_KEY = "watchlists:guided-tour:v1"

type GuidedTourTab = "sources" | "jobs" | "runs" | "items" | "outputs"
type GuidedTourStatus = "idle" | "in_progress" | "dismissed" | "completed"
interface GuidedTourState {
  status: GuidedTourStatus
  step: number
}

const GUIDED_TOUR_TABS: GuidedTourTab[] = ["sources", "jobs", "runs", "items", "outputs"]
const GUIDED_TOUR_LAST_STEP = GUIDED_TOUR_TABS.length - 1

const clampTourStep = (step: number): number => {
  if (!Number.isFinite(step)) return 0
  return Math.max(0, Math.min(Math.floor(step), GUIDED_TOUR_LAST_STEP))
}

const toGuidedTourStep = (step: number): 1 | 2 | 3 | 4 | 5 =>
  (clampTourStep(step) + 1) as 1 | 2 | 3 | 4 | 5

const readGuidedTourState = (): GuidedTourState => {
  if (typeof window === "undefined") return { status: "idle", step: 0 }
  try {
    const raw = localStorage.getItem(GUIDED_TOUR_STORAGE_KEY)
    if (!raw) return { status: "idle", step: 0 }
    const parsed = JSON.parse(raw) as Partial<GuidedTourState>
    const status =
      parsed.status === "in_progress" ||
      parsed.status === "dismissed" ||
      parsed.status === "completed"
        ? parsed.status
        : "idle"
    return { status, step: clampTourStep(Number(parsed.step || 0)) }
  } catch {
    return { status: "idle", step: 0 }
  }
}

const writeGuidedTourState = (state: GuidedTourState): void => {
  if (typeof window === "undefined") return
  try {
    localStorage.setItem(GUIDED_TOUR_STORAGE_KEY, JSON.stringify(state))
  } catch {
    // localStorage may be unavailable.
  }
}

const resolveRunNotificationsPollMs = (): number => {
  if (typeof window === "undefined") return RUN_NOTIFICATIONS_POLL_MS
  const override = Number(
    (window as { __TLDW_WATCHLISTS_RUN_NOTIFICATIONS_POLL_MS?: unknown })
      .__TLDW_WATCHLISTS_RUN_NOTIFICATIONS_POLL_MS
  )
  if (!Number.isFinite(override)) return RUN_NOTIFICATIONS_POLL_MS
  return Math.max(RUN_NOTIFICATIONS_MIN_POLL_MS, Math.floor(override))
}

const resolveWatchlistsIaExperimentEnabled = (): boolean => {
  if (typeof window !== "undefined") {
    const override = (window as { __TLDW_WATCHLISTS_IA_EXPERIMENT__?: unknown })
      .__TLDW_WATCHLISTS_IA_EXPERIMENT__
    if (typeof override === "boolean") return override
  }
  return process.env.NEXT_PUBLIC_WATCHLISTS_EXPERIMENTAL_IA === "true"
}

/**
 * WatchlistsPlaygroundPage
 *
 * Main container for the Watchlists module playground.
 * Provides a tabbed interface for managing sources, jobs, runs, outputs, templates, and settings.
 */
export const WatchlistsPlaygroundPage: React.FC = () => {
  const { t } = useTranslation(["watchlists", "common"])
  const isOnline = useServerOnline()
  const notification = useAntdNotification()

  const activeTab = useWatchlistsStore((s) => s.activeTab)
  const overviewHealth = useWatchlistsStore((s) => s.overviewHealth)
  const setActiveTab = useWatchlistsStore((s) => s.setActiveTab)
  const openRunDetail = useWatchlistsStore((s) => s.openRunDetail)
  const resetStore = useWatchlistsStore((s) => s.resetStore)
  const runStatusRef = useRef<Map<number, string>>(new Map())
  const notifiedRunStatesRef = useRef<Set<string>>(new Set())
  const initializedRunPollingRef = useRef(false)
  const runNotificationsTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const sessionStartedAtMsRef = useRef<number>(Date.now())
  const [guidedTourState, setGuidedTourState] = React.useState<GuidedTourState>(() => readGuidedTourState())
  const [guidedTourOpen, setGuidedTourOpen] = React.useState(false)
  const [showGuidedTourCompletion, setShowGuidedTourCompletion] = React.useState(false)
  const iaExperimentEnabled = React.useMemo(() => resolveWatchlistsIaExperimentEnabled(), [])
  const iaExperimentVariant = iaExperimentEnabled ? "experimental" : "baseline"
  const previousActiveTabRef = useRef<typeof activeTab | null>(null)

  const tabHelpLabels = {
    overview: t("watchlists:help.tabs.overview", "Overview guidance"),
    sources: t("watchlists:help.tabs.sources", "Feeds setup"),
    jobs: t("watchlists:help.tabs.jobs", "Monitor scheduling"),
    runs: t("watchlists:help.tabs.runs", "Activity guidance"),
    items: t("watchlists:help.tabs.items", "Article review"),
    outputs: t("watchlists:help.tabs.outputs", "Reports guidance"),
    templates: t("watchlists:help.tabs.templates", "Template authoring"),
    settings: t("watchlists:help.tabs.settings", "Workspace settings")
  } as const

  const taskShortcuts = [
    {
      key: "sources" as const,
      label: t("watchlists:quickActions.sources", "Set up feeds")
    },
    {
      key: "jobs" as const,
      label: t("watchlists:quickActions.jobs", "Configure monitors")
    },
    {
      key: "runs" as const,
      label: t("watchlists:quickActions.runs", "Check activity")
    },
    {
      key: "items" as const,
      label: t("watchlists:quickActions.items", "Review articles")
    },
    {
      key: "outputs" as const,
      label: t("watchlists:quickActions.outputs", "View reports")
    }
  ]

  const activeTabHelpHref = WATCHLISTS_TAB_HELP_DOCS[activeTab] || WATCHLISTS_MAIN_DOCS_URL
  const activeTabHelpLabel = tabHelpLabels[activeTab] || t("watchlists:help.docs", "Watchlists docs")

  const guidedTourSteps = [
    {
      tab: "sources" as const,
      title: t("watchlists:guide.steps.sources.title", "1. Add feeds"),
      description: t(
        "watchlists:guide.steps.sources.description",
        "Feeds are inputs for monitors. Add RSS/site sources before scheduling runs."
      )
    },
    {
      tab: "jobs" as const,
      title: t("watchlists:guide.steps.jobs.title", "2. Create monitors"),
      description: t(
        "watchlists:guide.steps.jobs.description",
        "Monitors turn feed inputs into scheduled runs and downstream outputs."
      )
    },
    {
      tab: "runs" as const,
      title: t("watchlists:guide.steps.runs.title", "3. Check activity"),
      description: t(
        "watchlists:guide.steps.runs.description",
        "Activity shows run status, logs, and failures for each monitor."
      )
    },
    {
      tab: "items" as const,
      title: t("watchlists:guide.steps.items.title", "4. Review articles"),
      description: t(
        "watchlists:guide.steps.items.description",
        "Articles are captured content from successful runs, ready for triage."
      )
    },
    {
      tab: "outputs" as const,
      title: t("watchlists:guide.steps.outputs.title", "5. Deliver reports"),
      description: t(
        "watchlists:guide.steps.outputs.description",
        "Reports contain generated briefings and delivery outcomes."
      )
    }
  ]
  const guidedTourStep = guidedTourSteps[clampTourStep(guidedTourState.step)]

  useEffect(() => {
    writeGuidedTourState(guidedTourState)
  }, [guidedTourState])

  const startGuidedTour = useCallback(() => {
    const nextState: GuidedTourState = { status: "in_progress", step: 0 }
    setGuidedTourState(nextState)
    setGuidedTourOpen(true)
    setShowGuidedTourCompletion(false)
    setActiveTab(GUIDED_TOUR_TABS[0])
    void trackWatchlistsOnboardingTelemetry({ type: "guided_tour_started" })
    void trackWatchlistsOnboardingTelemetry({ type: "guided_tour_step_viewed", step: 1 })
  }, [setActiveTab])

  const resumeGuidedTour = useCallback(() => {
    const step = clampTourStep(guidedTourState.step)
    setGuidedTourOpen(true)
    setActiveTab(GUIDED_TOUR_TABS[step])
    const stepNumber = toGuidedTourStep(step)
    void trackWatchlistsOnboardingTelemetry({ type: "guided_tour_resumed", step: stepNumber })
    void trackWatchlistsOnboardingTelemetry({ type: "guided_tour_step_viewed", step: stepNumber })
  }, [guidedTourState.step, setActiveTab])

  const handleSkipGuidedTour = useCallback(() => {
    setGuidedTourState((previous) => ({
      ...previous,
      status: "dismissed"
    }))
    setGuidedTourOpen(false)
    void trackWatchlistsOnboardingTelemetry({
      type: "guided_tour_dismissed",
      step: toGuidedTourStep(guidedTourState.step)
    })
  }, [guidedTourState.step])

  const handleGuidedTourBack = useCallback(() => {
    const nextStep = clampTourStep(guidedTourState.step - 1)
    setGuidedTourState({ status: "in_progress", step: nextStep })
    setActiveTab(GUIDED_TOUR_TABS[nextStep])
  }, [guidedTourState.step, setActiveTab])

  const handleGuidedTourNext = useCallback(() => {
    if (guidedTourState.step >= GUIDED_TOUR_LAST_STEP) {
      setGuidedTourState({ status: "completed", step: GUIDED_TOUR_LAST_STEP })
      setGuidedTourOpen(false)
      setShowGuidedTourCompletion(true)
      void trackWatchlistsOnboardingTelemetry({ type: "guided_tour_completed" })
      return
    }
    const nextStep = clampTourStep(guidedTourState.step + 1)
    setGuidedTourState({ status: "in_progress", step: nextStep })
    setActiveTab(GUIDED_TOUR_TABS[nextStep])
    void trackWatchlistsOnboardingTelemetry({
      type: "guided_tour_step_viewed",
      step: toGuidedTourStep(nextStep)
    })
  }, [guidedTourState.step, setActiveTab])

  // Reset store on unmount — use ref to avoid re-firing if selector returns new reference
  const resetStoreRef = useRef(resetStore)
  resetStoreRef.current = resetStore
  useEffect(() => {
    return () => {
      resetStoreRef.current()
    }
  }, [])

  const openRunFromNotification = useCallback((runId: number, key: string) => {
    notification.destroy(key)
    setActiveTab("runs")
    openRunDetail(runId)
  }, [notification, openRunDetail, setActiveTab])

  const openRunsTabFromNotification = useCallback((key: string) => {
    notification.destroy(key)
    setActiveTab("runs")
  }, [notification, setActiveTab])

  const showRunNotification = useCallback((run: WatchlistRun, kind: "completed" | "failed", hint?: string | null) => {
    const key = `watchlists-run-${run.id}-${run.status}`
    const onOpenRun = () => openRunFromNotification(run.id, key)
    const messageText = kind === "failed"
      ? t("watchlists:notifications.runFailedTitle", "Run failed")
      : t("watchlists:notifications.runCompletedTitle", "Run completed")
    const descriptionText = kind === "failed"
      ? t(
          "watchlists:notifications.runFailedDescription",
          "Run #{{id}} failed. {{hint}}",
          {
            id: run.id,
            hint: hint || getRunFailureHint(run.error_msg, t) || ""
          }
        )
      : t("watchlists:notifications.runCompletedDescription", "Run #{{id}} completed successfully.", {
          id: run.id
        })

    notification[kind === "failed" ? "error" : "success"]({
      key,
      message: messageText,
      description: descriptionText,
      placement: "bottomRight",
      duration: kind === "failed" ? 0 : 8,
      onClick: onOpenRun,
      btn: (
        <Button
          size="small"
          type="link"
          onClick={(event) => {
            event.preventDefault()
            event.stopPropagation()
            onOpenRun()
          }}
        >
          {t("watchlists:notifications.viewRun", "View run")}
        </Button>
      )
    })
  }, [notification, openRunFromNotification, t])

  const showGroupedRunNotification = useCallback(
    (group: { kind: "completed" | "failed" | "stalled"; count: number; deepLinkRunId: number; hint: string | null }) => {
      const key = `watchlists-run-group-${group.kind}-${group.deepLinkRunId}-${group.count}`
      const onOpenPrimaryRun = () => openRunFromNotification(group.deepLinkRunId, key)
      const onOpenActivity = () => openRunsTabFromNotification(key)

      const mode: "success" | "warning" | "error" =
        group.kind === "failed"
          ? "error"
          : group.kind === "stalled"
            ? "warning"
            : "success"
      const messageText =
        group.kind === "failed"
          ? t("watchlists:notifications.runFailedGroupedTitle", "Multiple runs failed")
          : group.kind === "stalled"
            ? t("watchlists:notifications.runStalledTitle", "Run appears stalled")
            : t("watchlists:notifications.runCompletedGroupedTitle", "Runs completed")
      const descriptionText =
        group.kind === "failed"
          ? t("watchlists:notifications.runFailedGroupedDescription", "{{count}} runs failed. {{hint}}", {
              count: group.count,
              hint: group.hint || t(
                "watchlists:notifications.failureHints.unknownEmpty",
                "Open run details to inspect logs and retry."
              )
            })
          : group.kind === "stalled"
            ? t("watchlists:notifications.runStalledDescription", "{{count}} runs appear stalled. {{hint}}", {
                count: group.count,
                hint: group.hint || t(
                  "watchlists:notifications.failureHints.stalled",
                  "Open Activity to inspect logs, then cancel or retry."
                )
              })
            : t("watchlists:notifications.runCompletedGroupedDescription", "{{count}} runs completed successfully.", {
                count: group.count
              })

      notification[mode]({
        key,
        message: messageText,
        description: descriptionText,
        placement: "bottomRight",
        duration: mode === "success" ? 8 : 0,
        onClick: onOpenPrimaryRun,
        btn: (
          <div className="flex items-center gap-2">
            <Button
              size="small"
              type="link"
              onClick={(event) => {
                event.preventDefault()
                event.stopPropagation()
                onOpenPrimaryRun()
              }}
            >
              {t("watchlists:notifications.viewRun", "View run")}
            </Button>
            <Button
              size="small"
              type="link"
              onClick={(event) => {
                event.preventDefault()
                event.stopPropagation()
                onOpenActivity()
              }}
            >
              {t("watchlists:notifications.openActivity", "Open Activity")}
            </Button>
          </div>
        )
      })
    },
    [notification, openRunFromNotification, openRunsTabFromNotification, t]
  )

  const pollRunNotifications = useCallback(async () => {
    try {
      const response = await fetchWatchlistRuns({
        page: 1,
        size: RUN_NOTIFICATIONS_PAGE_SIZE
      })
      const nextRuns = Array.isArray(response.items) ? response.items : []
      const previousStatusMap = runStatusRef.current
      const nextStatusMap = new Map<number, string>()
      const initialized = initializedRunPollingRef.current
      const nowMs = Date.now()
      const runById = new Map<number, WatchlistRun>()
      const candidateEvents: Array<{
        eventKey: string
        kind: "completed" | "failed" | "stalled"
        runId: number
        hint?: string | null
      }> = []

      nextRuns.forEach((run) => {
        runById.set(run.id, run)
        nextStatusMap.set(run.id, String(run.status || ""))
        const previousStatus = previousStatusMap.get(run.id)

        const transition = resolveRunTransitionNotification(previousStatus, run, t)
        if (initialized && transition) {
          candidateEvents.push({
            eventKey: buildRunStateNotificationKey(run.id, run.status),
            kind: transition.kind,
            runId: run.id,
            hint: transition.hint || null
          })
        }

        if (
          initialized &&
          !previousStatus &&
          shouldNotifyNewTerminalRun(run, sessionStartedAtMsRef.current)
        ) {
          const status = String(run.status || "").toLowerCase()
          const kind = status === "failed" ? "failed" : "completed"
          const hint = kind === "failed" ? getRunFailureHint(run.error_msg, t) : null
          candidateEvents.push({
            eventKey: buildRunStateNotificationKey(run.id, run.status),
            kind,
            runId: run.id,
            hint
          })
        }

        if (initialized) {
          const stalled = resolveStalledRunNotification(
            run,
            nowMs,
            RUN_STALLED_THRESHOLD_MS,
            t
          )
          if (stalled) {
            candidateEvents.push(stalled)
          }
        }
      })

      const freshEvents = dedupeRunNotificationEvents(
        candidateEvents,
        notifiedRunStatesRef.current
      )
      const groupedEvents = groupRunNotificationEvents(freshEvents)

      groupedEvents.forEach((group) => {
        if (group.count === 1 && group.kind !== "stalled") {
          const run = runById.get(group.deepLinkRunId)
          if (!run) return
          const event = freshEvents.find((entry) => entry.eventKey === group.eventKeys[0])
          showRunNotification(run, group.kind, event?.hint || group.hint)
          return
        }
        showGroupedRunNotification(group)
      })

      runStatusRef.current = nextStatusMap
      initializedRunPollingRef.current = true
    } catch (err) {
      console.debug("Watchlists run notification polling failed:", err)
    }
  }, [showGroupedRunNotification, showRunNotification, t])

  useEffect(() => {
    if (!isOnline) return
    const pollIntervalMs = resolveRunNotificationsPollMs()
    void pollRunNotifications()
    runNotificationsTimerRef.current = setInterval(() => {
      void pollRunNotifications()
    }, pollIntervalMs)
    return () => {
      if (runNotificationsTimerRef.current) {
        clearInterval(runNotificationsTimerRef.current)
        runNotificationsTimerRef.current = null
      }
    }
  }, [isOnline, pollRunNotifications])

  const overviewBadges = overviewHealth?.tabBadges || {
    sources: 0,
    runs: 0,
    outputs: 0
  }
  const tabAttentionBadge = (count: number): React.ReactNode =>
    count > 0 ? (
      <span
        className="inline-flex min-w-5 items-center justify-center rounded-full bg-red-500 px-1.5 text-[10px] font-semibold leading-4 text-white"
        aria-label={t("watchlists:tabs.attentionBadgeAria", "{{count}} attention items", { count })}
      >
        {count > 99 ? "99+" : count}
      </span>
    ) : null

  const tabItems: TabsProps["items"] = [
    {
      key: "overview",
      label: (
        <span className="flex items-center gap-2">
          <LayoutDashboard className="h-4 w-4" />
          {t("watchlists:tabs.overview", "Overview")}
        </span>
      ),
      children: <OverviewTab />
    },
    {
      key: "sources",
      label: (
        <span className="flex items-center gap-2">
          <Rss className="h-4 w-4" />
          {t("watchlists:tabs.sources", "Feeds")}
          {tabAttentionBadge(overviewBadges.sources)}
        </span>
      ),
      children: <SourcesTab />
    },
    {
      key: "jobs",
      label: (
        <span className="flex items-center gap-2">
          <CalendarClock className="h-4 w-4" />
          {t("watchlists:tabs.jobs", "Monitors")}
        </span>
      ),
      children: <JobsTab />
    },
    {
      key: "runs",
      label: (
        <span className="flex items-center gap-2">
          <Play className="h-4 w-4" />
          {t("watchlists:tabs.runs", "Activity")}
          {tabAttentionBadge(overviewBadges.runs)}
        </span>
      ),
      children: <RunsTab />
    },
    {
      key: "items",
      label: (
        <span className="flex items-center gap-2">
          <Newspaper className="h-4 w-4" />
          {t("watchlists:tabs.items", "Articles")}
        </span>
      ),
      children: <ItemsTab />
    },
    {
      key: "outputs",
      label: (
        <span className="flex items-center gap-2">
          <FileOutput className="h-4 w-4" />
          {t("watchlists:tabs.outputs", "Reports")}
          {tabAttentionBadge(overviewBadges.outputs)}
        </span>
      ),
      children: <OutputsTab />
    },
    {
      key: "templates",
      label: (
        <span className="flex items-center gap-2">
          <FileText className="h-4 w-4" />
          {t("watchlists:tabs.templates", "Templates")}
        </span>
      ),
      children: <TemplatesTab />
    },
    {
      key: "settings",
      label: (
        <span className="flex items-center gap-2">
          <Settings className="h-4 w-4" />
          {t("watchlists:tabs.settings", "Settings")}
        </span>
      ),
      children: <SettingsTab />
    }
  ]
  const reducedIaPrimaryTabKeys = ["overview", "sources", "runs", "outputs", "settings"] as const
  const reducedIaSecondaryTabKeys = ["jobs", "items", "templates"] as const
  const reducedIaSecondaryButtons = reducedIaSecondaryTabKeys.map((key) => ({
    key,
    label:
      key === "jobs"
        ? t("watchlists:tabs.jobs", "Monitors")
        : key === "items"
          ? t("watchlists:tabs.items", "Articles")
          : t("watchlists:tabs.templates", "Templates")
  }))
  const renderedTabItems: TabsProps["items"] = iaExperimentEnabled
    ? (() => {
        const primarySet = new Set<string>(reducedIaPrimaryTabKeys)
        const primaryItems = tabItems.filter((item) => item?.key && primarySet.has(String(item.key)))
        if (primarySet.has(activeTab)) return primaryItems
        const activeSecondaryItem = tabItems.find((item) => String(item?.key) === activeTab)
        if (!activeSecondaryItem) return primaryItems
        return [...primaryItems, activeSecondaryItem]
      })()
    : tabItems

  useEffect(() => {
    trackWatchlistsIaExperimentTransition(
      previousActiveTabRef.current,
      activeTab,
      iaExperimentVariant
    )
    previousActiveTabRef.current = activeTab
  }, [activeTab, iaExperimentVariant])

  if (!isOnline) {
    return (
      <PageShell className="py-6" maxWidthClassName="max-w-[1920px]">
        <Empty
          description={t(
            "watchlists:offline",
            "Server is offline. Please connect to use Watchlists."
          )}
        />
      </PageShell>
    )
  }

  return (
    <PageShell className="py-6" maxWidthClassName="max-w-[1920px]">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-text">
          {t("watchlists:title", "Watchlists")}
        </h1>
        <p className="mt-1 text-sm text-text-muted">
          {t(
            "watchlists:description",
            "Monitor RSS feeds, websites, and forums. Create scheduled monitors to automatically scrape and process content."
          )}
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
          <a
            href={WATCHLISTS_MAIN_DOCS_URL}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-primary hover:underline"
            data-testid="watchlists-main-docs-link"
          >
            {t("watchlists:help.docs", "Watchlists docs")}
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
          <a
            href={activeTabHelpHref}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-primary hover:underline"
            data-testid="watchlists-context-docs-link"
          >
            {t("watchlists:help.learnMoreTab", "Learn more: {{tab}}", {
              tab: activeTabHelpLabel
            })}
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
          {guidedTourState.status === "in_progress" ? (
            <Button
              size="small"
              type="default"
              onClick={resumeGuidedTour}
              data-testid="watchlists-resume-guide"
            >
              {t("watchlists:guide.resume", "Resume guided tour")}
            </Button>
          ) : (
            <Button
              size="small"
              type="default"
              onClick={startGuidedTour}
              data-testid="watchlists-start-guide"
            >
              {guidedTourState.status === "completed"
                ? t("watchlists:guide.restart", "Restart guided tour")
                : t("watchlists:guide.start", "Start guided tour")}
            </Button>
          )}
          {iaExperimentEnabled && (
            <div className="inline-flex flex-wrap items-center gap-2 border-l border-border pl-3 ml-1">
              <span className="text-text-muted">
                {t("watchlists:tabs.moreViews", "More views")}
              </span>
              {reducedIaSecondaryButtons.map((item) => (
                <Button
                  key={item.key}
                  size="small"
                  type={activeTab === item.key ? "primary" : "default"}
                  data-testid={`watchlists-experimental-tab-${item.key}`}
                  onClick={() => setActiveTab(item.key as typeof activeTab)}
                >
                  {item.label}
                </Button>
              ))}
            </div>
          )}
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
          <span className="text-text-muted">
            {t("watchlists:quickActions.label", "Jump to")}
          </span>
          {taskShortcuts.map((shortcut) => (
            <Button
              key={shortcut.key}
              size="small"
              type={activeTab === shortcut.key ? "primary" : "default"}
              onClick={() => setActiveTab(shortcut.key)}
              data-testid={`watchlists-task-open-${shortcut.key}`}
            >
              {shortcut.label}
            </Button>
          ))}
        </div>
      </div>

      {showGuidedTourCompletion && (
        <Alert
          type="success"
          showIcon
          className="mb-4"
          title={t("watchlists:guide.completedTitle", "Guided tour complete")}
          description={t(
            "watchlists:guide.completedDescription",
            "Next: monitor Activity for run health, review Articles for captured content, and open Reports for generated briefings."
          )}
          action={(
            <div className="flex flex-wrap gap-2">
              <Button size="small" onClick={() => setActiveTab("runs")}>
                {t("watchlists:guide.openActivity", "Open Activity")}
              </Button>
              <Button size="small" onClick={() => setActiveTab("items")}>
                {t("watchlists:guide.openArticles", "Open Articles")}
              </Button>
            </div>
          )}
          closable
          onClose={() => setShowGuidedTourCompletion(false)}
        />
      )}

      <DismissibleBetaAlert
        storageKey="beta-dismissed:watchlists"
        message={t("watchlists:betaNotice", "Beta Feature")}
        description={(
          <div className="space-y-1">
            <div>
              {t(
                "watchlists:betaDescription",
                "Watchlists is currently in beta. Some features may be incomplete or change."
              )}
            </div>
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <a
                href={WATCHLISTS_MAIN_DOCS_URL}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-primary hover:underline"
                data-testid="watchlists-beta-docs-link"
              >
                {t("watchlists:help.docs", "Watchlists docs")}
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
              <a
                href={WATCHLISTS_ISSUE_REPORT_URL}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-primary hover:underline"
                data-testid="watchlists-beta-report-link"
              >
                {t("watchlists:help.reportIssue", "Report an issue")}
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            </div>
          </div>
        )}
        className="mb-6"
      />

      <Tabs
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key as typeof activeTab)}
        items={renderedTabItems}
        className="watchlists-tabs"
      />

      <Modal
        open={guidedTourOpen}
        onCancel={handleSkipGuidedTour}
        title={t("watchlists:guide.title", "Watchlists guided tour")}
        footer={(
          <div className="flex items-center justify-between gap-2">
            <Button onClick={handleSkipGuidedTour}>
              {t("watchlists:guide.skip", "Skip")}
            </Button>
            <div className="flex items-center gap-2">
              <Button
                onClick={handleGuidedTourBack}
                disabled={guidedTourState.step === 0}
              >
                {t("common:back", "Back")}
              </Button>
              <Button
                type="primary"
                onClick={handleGuidedTourNext}
              >
                {guidedTourState.step >= GUIDED_TOUR_LAST_STEP
                  ? t("watchlists:guide.finish", "Finish")
                  : t("common:next", "Next")}
              </Button>
            </div>
          </div>
        )}
      >
        <div className="space-y-3">
          <div className="text-xs font-medium text-text-muted">
            {t("watchlists:guide.progress", "Step {{current}} of {{total}}", {
              current: clampTourStep(guidedTourState.step) + 1,
              total: guidedTourSteps.length
            })}
          </div>
          <div className="text-base font-semibold">{guidedTourStep.title}</div>
          <div className="text-sm text-text-muted">{guidedTourStep.description}</div>
        </div>
      </Modal>
    </PageShell>
  )
}
