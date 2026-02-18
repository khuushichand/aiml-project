import React, { useCallback, useEffect, useRef } from "react"
import { Button, Empty, Tabs } from "antd"
import { DismissibleBetaAlert } from "@/components/Common/DismissibleBetaAlert"
import type { TabsProps } from "antd"
import {
  CalendarClock,
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
  getRunFailureHint,
  resolveRunTransitionNotification,
  shouldNotifyNewTerminalRun
} from "./RunsTab/run-notifications"

const RUN_NOTIFICATIONS_POLL_MS = 15_000
const RUN_NOTIFICATIONS_PAGE_SIZE = 25
const RUN_NOTIFICATIONS_MIN_POLL_MS = 100

const resolveRunNotificationsPollMs = (): number => {
  if (typeof window === "undefined") return RUN_NOTIFICATIONS_POLL_MS
  const override = Number(
    (window as { __TLDW_WATCHLISTS_RUN_NOTIFICATIONS_POLL_MS?: unknown })
      .__TLDW_WATCHLISTS_RUN_NOTIFICATIONS_POLL_MS
  )
  if (!Number.isFinite(override)) return RUN_NOTIFICATIONS_POLL_MS
  return Math.max(RUN_NOTIFICATIONS_MIN_POLL_MS, Math.floor(override))
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
  const setActiveTab = useWatchlistsStore((s) => s.setActiveTab)
  const openRunDetail = useWatchlistsStore((s) => s.openRunDetail)
  const resetStore = useWatchlistsStore((s) => s.resetStore)
  const runStatusRef = useRef<Map<number, string>>(new Map())
  const notifiedRunStatesRef = useRef<Set<string>>(new Set())
  const initializedRunPollingRef = useRef(false)
  const runNotificationsTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const sessionStartedAtMsRef = useRef<number>(Date.now())

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
            hint: hint || getRunFailureHint(run.error_msg) || ""
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

      nextRuns.forEach((run) => {
        nextStatusMap.set(run.id, String(run.status || ""))
        const previousStatus = previousStatusMap.get(run.id)
        const runStateKey = `${run.id}:${String(run.status || "").toLowerCase()}`
        if (notifiedRunStatesRef.current.has(runStateKey)) return

        const transition = resolveRunTransitionNotification(previousStatus, run)
        if (initialized && transition) {
          notifiedRunStatesRef.current.add(runStateKey)
          showRunNotification(run, transition.kind, transition.hint)
          return
        }

        if (
          initialized &&
          !previousStatus &&
          shouldNotifyNewTerminalRun(run, sessionStartedAtMsRef.current)
        ) {
          const status = String(run.status || "").toLowerCase()
          const kind = status === "failed" ? "failed" : "completed"
          const hint = kind === "failed" ? getRunFailureHint(run.error_msg) : null
          notifiedRunStatesRef.current.add(runStateKey)
          showRunNotification(run, kind, hint)
        }
      })

      runStatusRef.current = nextStatusMap
      initializedRunPollingRef.current = true
    } catch (err) {
      console.debug("Watchlists run notification polling failed:", err)
    }
  }, [showRunNotification])

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
            "Monitor RSS feeds, websites, and forums. Create scheduled jobs to automatically scrape and process content."
          )}
        </p>
      </div>

      <DismissibleBetaAlert
        storageKey="beta-dismissed:watchlists"
        message={t("watchlists:betaNotice", "Beta Feature")}
        description={t(
          "watchlists:betaDescription",
          "Watchlists is currently in beta. Some features may be incomplete or change."
        )}
        className="mb-6"
      />

      <Tabs
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key as typeof activeTab)}
        items={tabItems}
        className="watchlists-tabs"
      />
    </PageShell>
  )
}
