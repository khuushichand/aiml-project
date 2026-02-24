import React, { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
  Alert,
  Button,
  Card,
  Empty,
  Form,
  Input,
  List,
  Modal,
  message,
  Select,
  Space,
  Steps,
  Spin,
  Statistic,
  Switch,
  Tag,
  Tooltip
} from "antd"
import {
  AlertTriangle,
  CheckCircle2,
  Newspaper,
  RefreshCw,
  Rss,
  Workflow
} from "lucide-react"
import { useTranslation } from "react-i18next"
import { useWatchlistsStore } from "@/store/watchlists"
import {
  createWatchlistJob,
  createWatchlistSource,
  testWatchlistSourceDraft,
  triggerWatchlistRun
} from "@/services/watchlists"
import {
  fetchWatchlistsOverviewData,
  getOverviewTabBadges,
  type WatchlistsOverviewData
} from "@/services/watchlists-overview"
import { formatRelativeTime } from "@/utils/dateFormatters"
import {
  QUICK_SETUP_DEFAULT_VALUES,
  type QuickSetupValues,
  toQuickSetupJobPayload,
  toQuickSetupSourcePayload
} from "./quick-setup"
import type { JobPreviewResult } from "@/types/watchlists"
import {
  trackWatchlistsOnboardingTelemetry,
  type WatchlistsQuickSetupStep
} from "@/utils/watchlists-onboarding-telemetry"

const OVERVIEW_REFRESH_INTERVAL_MS = 30_000
const QUICK_SETUP_MAX_STEP = 2
const QUICK_SETUP_STEP_KEYS: WatchlistsQuickSetupStep[] = ["feed", "monitor", "review"]
const QUICK_SETUP_STEP_FIELDS: Array<Array<keyof QuickSetupValues>> = [
  ["sourceName", "sourceUrl", "sourceType"],
  ["monitorName", "schedulePreset", "setupGoal", "audioBriefing", "runNow"],
  []
]

export const OverviewTab: React.FC = () => {
  const { t } = useTranslation(["watchlists", "common"])
  const [data, setData] = useState<WatchlistsOverviewData | null>(null)
  const [loading, setLoading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [quickSetupOpen, setQuickSetupOpen] = useState(false)
  const [quickSetupStep, setQuickSetupStep] = useState(0)
  const [quickSetupSubmitting, setQuickSetupSubmitting] = useState(false)
  const [quickSetupCandidatePreview, setQuickSetupCandidatePreview] = useState<JobPreviewResult | null>(null)
  const [quickSetupCandidatePreviewLoading, setQuickSetupCandidatePreviewLoading] = useState(false)
  const [quickSetupCandidatePreviewError, setQuickSetupCandidatePreviewError] = useState<string | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const quickSetupPreviewRequestRef = useRef(0)
  const [quickSetupForm] = Form.useForm<QuickSetupValues>()

  const setActiveTab = useWatchlistsStore((s) => s.setActiveTab)
  const setRunsStatusFilter = useWatchlistsStore((s) => s.setRunsStatusFilter)
  const setOverviewHealth = useWatchlistsStore((s) => s.setOverviewHealth)
  const openRunDetail = useWatchlistsStore((s) => s.openRunDetail)
  const openSourceForm = useWatchlistsStore((s) => s.openSourceForm)
  const openJobForm = useWatchlistsStore((s) => s.openJobForm)

  const loadOverview = useCallback(async (showLoading: boolean) => {
    if (showLoading) {
      setLoading(true)
    } else {
      setRefreshing(true)
    }
    try {
      const result = await fetchWatchlistsOverviewData()
      setData(result)
      if (typeof setOverviewHealth === "function") {
        setOverviewHealth(result.health, result.fetchedAt)
      }
      if (result.outputs.total > 0) {
        void trackWatchlistsOnboardingTelemetry({
          type: "quick_setup_first_run_succeeded",
          source: "overview"
        })
        void trackWatchlistsOnboardingTelemetry({
          type: "quick_setup_first_output_succeeded",
          source: "overview"
        })
      }
      setError(null)
    } catch (err) {
      console.error("Failed to load watchlists overview:", err)
      setError(t("watchlists:overview.fetchError", "Failed to load overview"))
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [setOverviewHealth, t])

  useEffect(() => {
    void loadOverview(true)
    intervalRef.current = setInterval(() => {
      void loadOverview(false)
    }, OVERVIEW_REFRESH_INTERVAL_MS)

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }, [loadOverview])

  const handleOpenRun = useCallback((runId: number) => {
    setActiveTab("runs")
    openRunDetail(runId)
  }, [openRunDetail, setActiveTab])

  const handleOpenItems = useCallback(() => {
    setActiveTab("items")
  }, [setActiveTab])

  const handleOpenJobs = useCallback(() => {
    setActiveTab("jobs")
  }, [setActiveTab])

  const handleOpenSources = useCallback(() => {
    setActiveTab("sources")
  }, [setActiveTab])

  const handleStartSourceQuickCreate = useCallback(() => {
    setActiveTab("sources")
    openSourceForm()
  }, [openSourceForm, setActiveTab])

  const handleStartJobQuickCreate = useCallback(() => {
    setActiveTab("jobs")
    openJobForm()
  }, [openJobForm, setActiveTab])

  const handleOpenRuns = useCallback(() => {
    setActiveTab("runs")
  }, [setActiveTab])

  const handleOpenFailedRuns = useCallback(() => {
    if (typeof setRunsStatusFilter === "function") {
      setRunsStatusFilter("failed")
    }
    setActiveTab("runs")
  }, [setActiveTab, setRunsStatusFilter])

  const handleOpenAttentionOutputs = useCallback(() => {
    setActiveTab("outputs")
  }, [setActiveTab])

  const handleOpenAttentionSources = useCallback(() => {
    setActiveTab("sources")
  }, [setActiveTab])

  const openQuickSetup = useCallback(() => {
    quickSetupForm.setFieldsValue(QUICK_SETUP_DEFAULT_VALUES)
    setQuickSetupStep(0)
    setQuickSetupOpen(true)
    void trackWatchlistsOnboardingTelemetry({ type: "quick_setup_opened" })
  }, [quickSetupForm])

  const closeQuickSetup = useCallback(() => {
    quickSetupPreviewRequestRef.current += 1
    setQuickSetupOpen(false)
    setQuickSetupStep(0)
    setQuickSetupCandidatePreview(null)
    setQuickSetupCandidatePreviewLoading(false)
    setQuickSetupCandidatePreviewError(null)
    quickSetupForm.resetFields()
  }, [quickSetupForm])

  const loadQuickSetupCandidatePreview = useCallback(async (draftValues?: Partial<QuickSetupValues>) => {
    const mergedValues = {
      ...QUICK_SETUP_DEFAULT_VALUES,
      ...quickSetupForm.getFieldsValue(true),
      ...(draftValues || {})
    } as QuickSetupValues
    const sourceUrl = String(mergedValues.sourceUrl || "").trim()
    if (!sourceUrl) {
      setQuickSetupCandidatePreview(null)
      setQuickSetupCandidatePreviewError(null)
      setQuickSetupCandidatePreviewLoading(false)
      return
    }

    const requestId = quickSetupPreviewRequestRef.current + 1
    quickSetupPreviewRequestRef.current = requestId
    setQuickSetupCandidatePreviewLoading(true)
    setQuickSetupCandidatePreviewError(null)

    try {
      const preview = await testWatchlistSourceDraft(
        {
          url: sourceUrl,
          source_type: mergedValues.sourceType || "rss"
        },
        { limit: 6 }
      )
      if (quickSetupPreviewRequestRef.current !== requestId) return
      setQuickSetupCandidatePreview(preview)
      setQuickSetupCandidatePreviewError(null)
      void trackWatchlistsOnboardingTelemetry({
        type: "quick_setup_preview_loaded",
        preview: "candidate",
        total: preview.total || 0,
        ingestable: preview.ingestable || 0,
        filtered: preview.filtered || 0
      })
    } catch (err) {
      console.error("Failed to load quick setup source preview:", err)
      if (quickSetupPreviewRequestRef.current !== requestId) return
      setQuickSetupCandidatePreview(null)
      setQuickSetupCandidatePreviewError(
        t(
          "watchlists:overview.onboarding.quickSetup.candidatePreview.error",
          "Could not load feed sample preview right now. You can still create setup and use a test run to verify results."
        )
      )
      void trackWatchlistsOnboardingTelemetry({
        type: "quick_setup_preview_failed",
        preview: "candidate",
        reason: "load_failed"
      })
    } finally {
      if (quickSetupPreviewRequestRef.current === requestId) {
        setQuickSetupCandidatePreviewLoading(false)
      }
    }
  }, [quickSetupForm, t])

  const getQuickSetupStepKey = useCallback(
    (step: number): WatchlistsQuickSetupStep => {
      const clamped = Math.max(0, Math.min(step, QUICK_SETUP_MAX_STEP))
      return QUICK_SETUP_STEP_KEYS[clamped]
    },
    []
  )

  const cancelQuickSetup = useCallback(() => {
    void trackWatchlistsOnboardingTelemetry({
      type: "quick_setup_cancelled",
      step: getQuickSetupStepKey(quickSetupStep)
    })
    closeQuickSetup()
  }, [closeQuickSetup, getQuickSetupStepKey, quickSetupStep])

  const handleQuickSetupNext = useCallback(async () => {
    const fields = QUICK_SETUP_STEP_FIELDS[quickSetupStep] || []
    if (fields.length > 0) {
      await quickSetupForm.validateFields(fields)
    }
    void trackWatchlistsOnboardingTelemetry({
      type: "quick_setup_step_completed",
      step: getQuickSetupStepKey(quickSetupStep)
    })
    if (quickSetupStep === 0) {
      const sourceName = String(quickSetupForm.getFieldValue("sourceName") || "").trim()
      const monitorName = String(quickSetupForm.getFieldValue("monitorName") || "").trim()
      if (sourceName.length > 0 && monitorName.length === 0) {
        quickSetupForm.setFieldsValue({
          monitorName: `${sourceName} Monitor`
        })
      }
    }
    if (quickSetupStep === 1) {
      const values = {
        ...QUICK_SETUP_DEFAULT_VALUES,
        ...quickSetupForm.getFieldsValue(true)
      } as QuickSetupValues
      void trackWatchlistsOnboardingTelemetry({
        type: "quick_setup_preview_loaded",
        preview: "template",
        goal: values.setupGoal,
        audioEnabled: values.audioBriefing
      })
    }
    setQuickSetupStep((prev) => Math.min(prev + 1, QUICK_SETUP_MAX_STEP))
  }, [getQuickSetupStepKey, quickSetupForm, quickSetupStep, t])

  const handleQuickSetupBack = useCallback(() => {
    setQuickSetupStep((prev) => Math.max(prev - 1, 0))
  }, [])

  const completeQuickSetup = useCallback(async () => {
    const currentStep = getQuickSetupStepKey(quickSetupStep)
    void trackWatchlistsOnboardingTelemetry({
      type: "quick_setup_step_completed",
      step: currentStep
    })
    try {
      const values = {
        ...QUICK_SETUP_DEFAULT_VALUES,
        ...quickSetupForm.getFieldsValue(true)
      } as QuickSetupValues
      setQuickSetupSubmitting(true)

      const source = await createWatchlistSource(
        toQuickSetupSourcePayload(values)
      )

      const job = await createWatchlistJob(
        toQuickSetupJobPayload(values, source.id)
      )

      let runId: number | null = null
      if (values.runNow) {
        try {
          const run = await triggerWatchlistRun(job.id)
          runId = run.id
          void trackWatchlistsOnboardingTelemetry({
            type: "quick_setup_test_run_triggered",
            runId: run.id
          })
        } catch (runError) {
          void trackWatchlistsOnboardingTelemetry({
            type: "quick_setup_test_run_failed"
          })
          throw runError
        }
      }

      message.success(
        values.runNow
          ? t(
              "watchlists:overview.onboarding.quickSetup.testRunPending",
              "Quick setup complete. Test run started. Open Activity for progress and Reports for generated briefings."
            )
          : values.setupGoal === "briefing"
            ? t(
                "watchlists:overview.onboarding.quickSetup.createdBriefing",
                "Quick setup complete. Feed and monitor created for briefing reports."
              )
          : t(
              "watchlists:overview.onboarding.quickSetup.created",
              "Quick setup complete. Feed and monitor created."
            )
      )

      closeQuickSetup()
      void loadOverview(false)

      if (runId != null) {
        setActiveTab("runs")
        openRunDetail(runId)
        void trackWatchlistsOnboardingTelemetry({
          type: "quick_setup_completed",
          goal: values.setupGoal,
          runNow: true,
          destination: "runs"
        })
      } else if (values.setupGoal === "briefing") {
        setActiveTab("outputs")
        void trackWatchlistsOnboardingTelemetry({
          type: "quick_setup_completed",
          goal: values.setupGoal,
          runNow: false,
          destination: "outputs"
        })
      } else {
        setActiveTab("jobs")
        void trackWatchlistsOnboardingTelemetry({
          type: "quick_setup_completed",
          goal: values.setupGoal,
          runNow: false,
          destination: "jobs"
        })
      }
    } catch (err) {
      console.error("Failed to complete quick setup:", err)
      void trackWatchlistsOnboardingTelemetry({
        type: "quick_setup_failed",
        step: currentStep
      })
      message.error(
        t(
          "watchlists:overview.onboarding.quickSetup.error",
          "Failed to complete quick setup."
        )
      )
    } finally {
      setQuickSetupSubmitting(false)
    }
  }, [
    closeQuickSetup,
    getQuickSetupStepKey,
    loadOverview,
    openRunDetail,
    quickSetupForm,
    quickSetupStep,
    setActiveTab,
    t
  ])

  const quickSetupValues = Form.useWatch([], quickSetupForm) as Partial<QuickSetupValues> | undefined
  const quickSetupSnapshot = useMemo(
    () =>
      ({
        ...QUICK_SETUP_DEFAULT_VALUES,
        ...quickSetupForm.getFieldsValue(true),
        ...(quickSetupValues || {})
      }) as QuickSetupValues,
    [quickSetupForm, quickSetupValues]
  )

  useEffect(() => {
    if (!quickSetupOpen || quickSetupStep !== QUICK_SETUP_MAX_STEP) return
    void loadQuickSetupCandidatePreview(quickSetupSnapshot)
  }, [
    loadQuickSetupCandidatePreview,
    quickSetupOpen,
    quickSetupStep,
    quickSetupSnapshot.sourceType,
    quickSetupSnapshot.sourceUrl
  ])

  const quickSetupCandidateSummary = useMemo(() => {
    if (quickSetupCandidatePreviewLoading) {
      return t(
        "watchlists:overview.onboarding.quickSetup.candidatePreview.loading",
        "Loading sample candidates..."
      )
    }
    if (quickSetupCandidatePreviewError) return quickSetupCandidatePreviewError
    if (!quickSetupCandidatePreview) {
      return t(
        "watchlists:overview.onboarding.quickSetup.candidatePreview.empty",
        "No sample candidates returned yet. You can still create setup and validate with a test run."
      )
    }
    return t(
      "watchlists:overview.onboarding.quickSetup.candidatePreview.summary",
      "{{ingestable}} ingestable, {{filtered}} filtered from {{total}} sample items.",
      {
        ingestable: quickSetupCandidatePreview.ingestable,
        filtered: quickSetupCandidatePreview.filtered,
        total: quickSetupCandidatePreview.total
      }
    )
  }, [
    quickSetupCandidatePreview,
    quickSetupCandidatePreviewError,
    quickSetupCandidatePreviewLoading,
    t
  ])

  const quickSetupTemplatePreview = useMemo(() => {
    if (quickSetupSnapshot.setupGoal === "triage") {
      return t(
        "watchlists:overview.onboarding.quickSetup.templatePreview.none",
        "No briefing output will be generated for feed-review-only setup."
      )
    }

    const monitorName = String(quickSetupSnapshot.monitorName || "").trim() || "Briefing"
    const sourceName = String(quickSetupSnapshot.sourceName || "").trim() || "Selected feed"
    const topItems = (quickSetupCandidatePreview?.items || [])
      .slice(0, 3)
      .map((item) => item.title || item.url || `Source #${item.source_id}`)

    return [
      `# ${monitorName}`,
      "",
      `Source: ${sourceName}`,
      "",
      "Top candidate headlines:",
      ...(topItems.length > 0
        ? topItems.map((item, index) => `${index + 1}. ${item}`)
        : ["1. Headlines will appear after the first run completes."]),
      "",
      `Audio briefing: ${quickSetupSnapshot.audioBriefing ? "Enabled" : "Disabled"}`
    ].join("\n")
  }, [
    quickSetupCandidatePreview,
    quickSetupSnapshot.audioBriefing,
    quickSetupSnapshot.monitorName,
    quickSetupSnapshot.setupGoal,
    quickSetupSnapshot.sourceName,
    t
  ])

  const quickSetupDestinationHint = useMemo(() => {
    if (quickSetupSnapshot.runNow) {
      return t(
        "watchlists:overview.onboarding.quickSetup.destinationHint.runNow",
        "Starts one test run immediately and opens Activity details."
      )
    }
    if (quickSetupSnapshot.setupGoal === "briefing") {
      return t(
        "watchlists:overview.onboarding.quickSetup.destinationHint.briefing",
        "Opens Reports after setup. Use Run now in Monitors if you want immediate output."
      )
    }
    return t(
      "watchlists:overview.onboarding.quickSetup.destinationHint.triage",
      "Opens Monitors after setup so you can run checks when ready."
    )
  }, [quickSetupSnapshot.runNow, quickSetupSnapshot.setupGoal, t])

  const quickSetupIsLastStep = quickSetupStep >= QUICK_SETUP_MAX_STEP
  const quickSetupFinishLabel = quickSetupSnapshot.runNow
    ? t(
        "watchlists:overview.onboarding.quickSetup.actions.finishWithTest",
        "Create setup + run test"
      )
    : t("watchlists:overview.onboarding.quickSetup.actions.finish", "Create setup")
  const quickSetupStepHelp =
    quickSetupStep === 0
      ? t(
          "watchlists:overview.onboarding.quickSetup.help.feed",
          "Tip: paste a feed URL now. You can adjust feed settings later."
        )
      : quickSetupStep === 1
        ? t(
            "watchlists:overview.onboarding.quickSetup.help.monitor",
            "No cron needed: choose a preset schedule for now."
          )
        : t(
            "watchlists:overview.onboarding.quickSetup.help.review",
            "You can change any of these settings later from Feeds and Monitors."
          )
  const overviewBadges = getOverviewTabBadges(data?.health)

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center py-16">
        <Spin size="large" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-text-muted">
          {t(
            "watchlists:overview.description",
            "At-a-glance watchlist health, activity, and failure signals."
          )}
        </p>
        <Space size="small">
          {data?.fetchedAt && (
            <Tooltip title={new Date(data.fetchedAt).toLocaleString()}>
              <span className="text-xs text-text-muted">
                {t("watchlists:overview.lastUpdated", "Updated {{time}}", {
                  time: formatRelativeTime(data.fetchedAt, t, { compact: true })
                })}
              </span>
            </Tooltip>
          )}
          <Button
            icon={<RefreshCw className="h-4 w-4" />}
            onClick={() => void loadOverview(false)}
            loading={refreshing}
          >
            {t("common:refresh", "Refresh")}
          </Button>
        </Space>
      </div>

      {error && (
        <Alert type="error" showIcon title={error} />
      )}

      {data && (
        <>
          {(data.sources.total === 0 || data.jobs.total === 0) && (
            <Card
              size="small"
              title={t("watchlists:overview.onboarding.title", "Quick setup")}
            >
              <p className="mb-3 text-sm text-text-muted">
                {t(
                  "watchlists:overview.onboarding.pipeline",
                  "Add Feed -> Create Monitor -> Review Results"
                )}
              </p>
              <Steps
                size="small"
                current={data.sources.total === 0 ? 0 : data.jobs.total === 0 ? 1 : 2}
                items={[
                  {
                    title: t("watchlists:overview.onboarding.steps.addFeed.title", "Add your first feed"),
                    content: t(
                      "watchlists:overview.onboarding.steps.addFeed.description",
                      "Start by adding an RSS/site source in Feeds."
                    )
                  },
                  {
                    title: t("watchlists:overview.onboarding.steps.createMonitor.title", "Create your first monitor"),
                    content: t(
                      "watchlists:overview.onboarding.steps.createMonitor.description",
                      "Pick feeds, then set a schedule with presets."
                    )
                  },
                  {
                    title: t("watchlists:overview.onboarding.steps.reviewResults.title", "Review results"),
                    content: t(
                      "watchlists:overview.onboarding.steps.reviewResults.description",
                      "Open Articles for content and Activity for run diagnostics."
                    )
                  }
                ]}
              />
              <Space className="mt-4" wrap>
                <Button
                  onClick={openQuickSetup}
                  data-testid="watchlists-overview-cta-guided-setup"
                >
                  {t("watchlists:overview.onboarding.cta.guidedSetup", "Guided setup")}
                </Button>
                {data.sources.total === 0 && (
                  <Button
                    type="primary"
                    onClick={handleStartSourceQuickCreate}
                    data-testid="watchlists-overview-cta-add-feed"
                  >
                    {t("watchlists:overview.onboarding.cta.addFeed", "Add first feed")}
                  </Button>
                )}
                {data.sources.total > 0 && data.jobs.total === 0 && (
                  <Button
                    type="primary"
                    onClick={handleStartJobQuickCreate}
                    data-testid="watchlists-overview-cta-create-monitor"
                  >
                    {t("watchlists:overview.onboarding.cta.createMonitor", "Create first monitor")}
                  </Button>
                )}
                <Button onClick={handleOpenItems}>
                  {t("watchlists:overview.onboarding.cta.reviewArticles", "Open Articles")}
                </Button>
              </Space>
            </Card>
          )}

          <Alert
            showIcon
            type={data.systemHealth === "degraded" ? "warning" : "success"}
            title={
              data.systemHealth === "degraded"
                ? t("watchlists:overview.health.degradedTitle", "System requires attention")
                : t("watchlists:overview.health.healthyTitle", "System healthy")
            }
            description={
              data.systemHealth === "degraded"
                ? t(
                    "watchlists:overview.health.degradedDescription",
                    "Some sources or recent runs show failures. Open failed runs to investigate."
                  )
                : t(
                    "watchlists:overview.health.healthyDescription",
                    "No recent failed runs and source health is stable."
                  )
            }
          />

          {data.health.attention.total > 0 && (
            <Card
              size="small"
              title={t("watchlists:overview.attention.title", "Attention needed")}
            >
              <p className="mb-3 text-sm text-text-muted">
                {t(
                  "watchlists:overview.attention.description",
                  "Open the highest-risk surfaces directly from here."
                )}
              </p>
              <Space wrap>
                {overviewBadges.sources > 0 && (
                  <Button
                    danger
                    onClick={handleOpenAttentionSources}
                    data-testid="watchlists-overview-attention-sources"
                  >
                    {t("watchlists:overview.attention.sources", "Feeds need review ({{count}})", {
                      count: overviewBadges.sources
                    })}
                  </Button>
                )}
                {overviewBadges.runs > 0 && (
                  <Button
                    danger
                    onClick={handleOpenFailedRuns}
                    data-testid="watchlists-overview-attention-runs"
                  >
                    {t("watchlists:overview.attention.runs", "Failed activity runs ({{count}})", {
                      count: overviewBadges.runs
                    })}
                  </Button>
                )}
                {overviewBadges.outputs > 0 && (
                  <Button
                    danger
                    onClick={handleOpenAttentionOutputs}
                    data-testid="watchlists-overview-attention-outputs"
                  >
                    {t("watchlists:overview.attention.outputs", "Reports with delivery issues ({{count}})", {
                      count: overviewBadges.outputs
                    })}
                  </Button>
                )}
                {data.jobs.attention > 0 && (
                  <Button
                    onClick={handleOpenJobs}
                    data-testid="watchlists-overview-attention-jobs"
                  >
                    {t("watchlists:overview.attention.jobs", "Monitors need schedule fixes ({{count}})", {
                      count: data.jobs.attention
                    })}
                  </Button>
                )}
              </Space>
            </Card>
          )}

          {data.sources.total > 0 && data.jobs.total > 0 && (
            <Alert
              showIcon
              type="info"
              title={t("watchlists:overview.setupComplete.title", "Setup complete")}
              description={
                data.jobs.nextRunAt
                  ? t(
                      "watchlists:overview.setupComplete.nextRunDescription",
                      "Your next monitor run is {{time}}. New content will appear in Articles and Activity.",
                      { time: formatRelativeTime(data.jobs.nextRunAt, t) }
                    )
                  : t(
                      "watchlists:overview.setupComplete.runNowDescription",
                      "Run a monitor from Monitors to generate your first Articles and Activity entries."
                    )
              }
              action={
                <Button size="small" onClick={handleOpenRuns}>
                  {t("watchlists:overview.setupComplete.openActivity", "Open Activity")}
                </Button>
              }
            />
          )}

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <Card
              size="small"
              title={(
                <span className="flex items-center gap-2">
                  <Rss className="h-4 w-4" />
                  {t("watchlists:overview.cards.sources.title", "Feeds")}
                </span>
              )}
              extra={(
                <Button type="link" size="small" onClick={handleOpenSources}>
                  {t("watchlists:overview.openSources", "Open")}
                </Button>
              )}
            >
              <Statistic
                value={data.sources.total}
                title={t("watchlists:overview.cards.sources.total", "Total")}
              />
              <div className="mt-3 flex flex-wrap gap-2">
                <Tag color="green">
                  {t("watchlists:overview.cards.sources.healthy", "Healthy {{count}}", {
                    count: data.sources.healthy
                  })}
                </Tag>
                <Tag color={data.sources.degraded > 0 ? "red" : "default"}>
                  {t("watchlists:overview.cards.sources.degraded", "Degraded {{count}}", {
                    count: data.sources.degraded
                  })}
                </Tag>
                <Tag>
                  {t("watchlists:overview.cards.sources.inactive", "Inactive {{count}}", {
                    count: data.sources.inactive
                  })}
                </Tag>
              </div>
            </Card>

            <Card
              size="small"
              title={(
                <span className="flex items-center gap-2">
                  <Workflow className="h-4 w-4" />
                  {t("watchlists:overview.cards.jobs.title", "Monitors")}
                </span>
              )}
              extra={(
                <Button type="link" size="small" onClick={handleOpenJobs}>
                  {t("watchlists:overview.openJobs", "Open")}
                </Button>
              )}
            >
              <Statistic
                value={data.jobs.active}
                title={t("watchlists:overview.cards.jobs.active", "Active")}
                suffix={`/ ${data.jobs.total}`}
              />
              <div className="mt-3 text-xs text-text-muted">
                {data.jobs.nextRunAt
                  ? t("watchlists:overview.cards.jobs.nextRun", "Next run {{time}}", {
                      time: formatRelativeTime(data.jobs.nextRunAt, t, { compact: true })
                    })
                  : t("watchlists:overview.cards.jobs.noNextRun", "No upcoming schedules")}
              </div>
            </Card>

            <Card
              size="small"
              title={(
                <span className="flex items-center gap-2">
                  <Newspaper className="h-4 w-4" />
                  {t("watchlists:overview.cards.items.title", "Articles")}
                </span>
              )}
              extra={(
                <Button type="link" size="small" onClick={handleOpenItems}>
                  {t("watchlists:overview.openItems", "Open")}
                </Button>
              )}
            >
              <Statistic
                value={data.items.unread}
                title={t("watchlists:overview.cards.items.unread", "Unread")}
              />
            </Card>

            <Card
              size="small"
              title={(
                <span className="flex items-center gap-2">
                  {data.runs.running + data.runs.pending > 0 ? (
                    <AlertTriangle className="h-4 w-4 text-warning" />
                  ) : (
                    <CheckCircle2 className="h-4 w-4 text-success" />
                  )}
                  {t("watchlists:overview.cards.runs.title", "Activity")}
                </span>
              )}
              extra={(
                <Button type="link" size="small" onClick={() => setActiveTab("runs")}>
                  {t("watchlists:overview.openRuns", "Open")}
                </Button>
              )}
            >
              <Statistic
                value={data.runs.running}
                title={t("watchlists:overview.cards.runs.running", "Running")}
              />
              <div className="mt-3 text-xs text-text-muted">
                {t("watchlists:overview.cards.runs.pending", "Pending {{count}}", {
                  count: data.runs.pending
                })}
              </div>
            </Card>
          </div>

          <Card
            size="small"
            title={t("watchlists:overview.failedRuns.title", "Recent Failed Runs")}
          >
            {data.runs.recentFailed.length === 0 ? (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={t("watchlists:overview.failedRuns.empty", "No recent failures")}
              />
            ) : (
              <List
                dataSource={data.runs.recentFailed}
                renderItem={(run) => (
                  <List.Item
                    actions={[
                      <Button
                        key={`open-${run.id}`}
                        size="small"
                        type="link"
                        onClick={() => handleOpenRun(run.id)}
                      >
                        {t("watchlists:overview.failedRuns.viewRun", "View run")}
                      </Button>
                    ]}
                  >
                    <List.Item.Meta
                      title={(
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium">
                            {run.job_name ||
                              t("watchlists:overview.failedRuns.jobFallback", "Monitor #{{id}}", {
                                id: run.job_id
                              })}
                          </span>
                          <Tag color="red">{t("watchlists:overview.failedRuns.failed", "Failed")}</Tag>
                          {run.finished_at && (
                            <span className="text-xs text-text-muted">
                              {formatRelativeTime(run.finished_at, t)}
                            </span>
                          )}
                        </div>
                      )}
                      description={
                        run.error_msg || t("watchlists:overview.failedRuns.noError", "No error details available")
                      }
                    />
                  </List.Item>
                )}
              />
            )}
          </Card>
        </>
      )}

      <Modal
        open={quickSetupOpen}
        title={t("watchlists:overview.onboarding.quickSetup.title", "Guided quick setup")}
        onCancel={quickSetupSubmitting ? undefined : cancelQuickSetup}
        destroyOnHidden
        maskClosable={!quickSetupSubmitting}
        footer={[
          <Button
            key="cancel"
            onClick={cancelQuickSetup}
            disabled={quickSetupSubmitting}
          >
            {t("common:cancel", "Cancel")}
          </Button>,
          <Button
            key="back"
            onClick={handleQuickSetupBack}
            disabled={quickSetupSubmitting || quickSetupStep === 0}
          >
            {t("common:back", "Back")}
          </Button>,
          <Button
            key="next"
            type="primary"
            loading={quickSetupSubmitting}
            onClick={() => {
              if (quickSetupIsLastStep) {
                void completeQuickSetup()
              } else {
                void handleQuickSetupNext()
              }
            }}
          >
            {quickSetupIsLastStep
              ? quickSetupFinishLabel
              : t("common:next", "Next")}
          </Button>
        ]}
      >
        <div className="space-y-4">
          <Steps
            size="small"
            current={quickSetupStep}
            items={[
              { title: t("watchlists:overview.onboarding.quickSetup.steps.feed", "Feed") },
              { title: t("watchlists:overview.onboarding.quickSetup.steps.monitor", "Monitor") },
              { title: t("watchlists:overview.onboarding.quickSetup.steps.review", "Review") }
            ]}
          />
          <div className="rounded-md border border-border bg-surface px-3 py-2 text-xs text-text-muted">
            {quickSetupStepHelp}
          </div>

          <Form
            form={quickSetupForm}
            layout="vertical"
            initialValues={QUICK_SETUP_DEFAULT_VALUES}
          >
            {quickSetupStep === 0 && (
              <div className="space-y-1">
                <Form.Item
                  label={t("watchlists:overview.onboarding.quickSetup.fields.sourceName", "Feed name")}
                  name="sourceName"
                  rules={[
                    {
                      required: true,
                      message: t(
                        "watchlists:overview.onboarding.quickSetup.validation.sourceNameRequired",
                        "Enter a feed name"
                      )
                    }
                  ]}
                >
                  <Input
                    placeholder={t(
                      "watchlists:overview.onboarding.quickSetup.placeholders.sourceName",
                      "e.g., Daily Tech Feed"
                    )}
                    autoFocus
                  />
                </Form.Item>

                <Form.Item
                  label={t("watchlists:overview.onboarding.quickSetup.fields.sourceUrl", "Feed URL")}
                  name="sourceUrl"
                  rules={[
                    {
                      required: true,
                      message: t(
                        "watchlists:overview.onboarding.quickSetup.validation.sourceUrlRequired",
                        "Enter a feed URL"
                      )
                    },
                    {
                      validator: (_rule, value) => {
                        const raw = String(value || "").trim()
                        if (!raw) return Promise.resolve()
                        try {
                          const parsed = new URL(raw)
                          if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
                            throw new Error("invalid_protocol")
                          }
                          return Promise.resolve()
                        } catch {
                          return Promise.reject(
                            new Error(
                              t(
                                "watchlists:overview.onboarding.quickSetup.validation.sourceUrlInvalid",
                                "Enter a valid http(s) URL"
                              )
                            )
                          )
                        }
                      }
                    }
                  ]}
                >
                  <Input
                    placeholder={t(
                      "watchlists:overview.onboarding.quickSetup.placeholders.sourceUrl",
                      "https://example.com/feed.xml"
                    )}
                  />
                </Form.Item>

                <Form.Item
                  label={t("watchlists:overview.onboarding.quickSetup.fields.sourceType", "Feed type")}
                  name="sourceType"
                >
                  <Select
                    options={[
                      {
                        value: "rss",
                        label: t("watchlists:sources.types.rss", "RSS Feed")
                      },
                      {
                        value: "site",
                        label: t("watchlists:sources.types.site", "Website")
                      },
                      {
                        value: "forum",
                        label: t("watchlists:sources.types.forumComingSoon", "Forum (coming soon)"),
                        disabled: true
                      }
                    ]}
                  />
                </Form.Item>
              </div>
            )}

            {quickSetupStep === 1 && (
              <div className="space-y-1">
                <Form.Item
                  label={t("watchlists:overview.onboarding.quickSetup.fields.monitorName", "Monitor name")}
                  name="monitorName"
                  rules={[
                    {
                      required: true,
                      message: t(
                        "watchlists:overview.onboarding.quickSetup.validation.monitorNameRequired",
                        "Enter a monitor name"
                      )
                    }
                  ]}
                >
                  <Input
                    placeholder={t(
                      "watchlists:overview.onboarding.quickSetup.placeholders.monitorName",
                      "e.g., Morning Brief"
                    )}
                    autoFocus
                  />
                </Form.Item>

                <Form.Item
                  label={t("watchlists:overview.onboarding.quickSetup.fields.schedule", "Schedule")}
                  name="schedulePreset"
                >
                  <Select
                    options={[
                      {
                        value: "none",
                        label: t("watchlists:overview.onboarding.quickSetup.schedule.none", "Manual only")
                      },
                      {
                        value: "hourly",
                        label: t("watchlists:overview.onboarding.quickSetup.schedule.hourly", "Hourly")
                      },
                      {
                        value: "daily",
                        label: t("watchlists:overview.onboarding.quickSetup.schedule.daily", "Daily at 08:00")
                      },
                      {
                        value: "weekdays",
                        label: t("watchlists:overview.onboarding.quickSetup.schedule.weekdays", "Weekdays at 08:00")
                      }
                    ]}
                  />
                </Form.Item>

                <Form.Item
                  label={t("watchlists:overview.onboarding.quickSetup.fields.setupGoal", "Setup goal")}
                  name="setupGoal"
                >
                  <Select
                    options={[
                      {
                        value: "briefing",
                        label: t(
                          "watchlists:overview.onboarding.quickSetup.goal.briefing",
                          "Generate briefing reports"
                        )
                      },
                      {
                        value: "triage",
                        label: t(
                          "watchlists:overview.onboarding.quickSetup.goal.triage",
                          "Feed review only"
                        )
                      }
                    ]}
                  />
                </Form.Item>

                <Form.Item
                  label={t("watchlists:overview.onboarding.quickSetup.fields.audioBriefing", "Audio briefing")}
                  name="audioBriefing"
                  valuePropName="checked"
                >
                  <Switch />
                </Form.Item>
                <div className="-mt-3 mb-2 text-xs text-text-muted">
                  {t(
                    "watchlists:overview.onboarding.quickSetup.hints.audioBriefing",
                    "Enable spoken briefings alongside text reports."
                  )}
                </div>

                <Form.Item
                  label={t(
                    "watchlists:overview.onboarding.quickSetup.fields.runNow",
                    "Run test generation immediately"
                  )}
                  name="runNow"
                  valuePropName="checked"
                >
                  <Switch />
                </Form.Item>
                <div className="-mt-3 text-xs text-text-muted">
                  {t(
                    "watchlists:overview.onboarding.quickSetup.hints.runNow",
                    "Runs one test generation after setup so you can verify results before waiting for the next schedule."
                  )}
                </div>
              </div>
            )}

            {quickSetupStep === 2 && (
              <div className="space-y-3 text-sm">
                <p className="text-text-muted">
                  {t(
                    "watchlists:overview.onboarding.quickSetup.reviewDescription",
                    "Preview sample candidates and expected briefing, then create your feed and monitor."
                  )}
                </p>
                <div className="rounded-md border border-border bg-surface p-3">
                  <p>
                    <span className="font-medium">
                      {t("watchlists:overview.onboarding.quickSetup.review.feed", "Feed")}:
                    </span>{" "}
                    {quickSetupSnapshot.sourceName || "—"}
                  </p>
                  <p className="text-text-muted">
                    {quickSetupSnapshot.sourceUrl || "—"}
                  </p>
                  <p className="mt-2">
                    <span className="font-medium">
                      {t("watchlists:overview.onboarding.quickSetup.review.monitor", "Monitor")}:
                    </span>{" "}
                    {quickSetupSnapshot.monitorName || "—"}
                  </p>
                  <p>
                    <span className="font-medium">
                      {t("watchlists:overview.onboarding.quickSetup.review.schedule", "Schedule")}:
                    </span>{" "}
                    {quickSetupSnapshot.schedulePreset === "hourly"
                      ? t("watchlists:overview.onboarding.quickSetup.schedule.hourly", "Hourly")
                      : quickSetupSnapshot.schedulePreset === "daily"
                        ? t("watchlists:overview.onboarding.quickSetup.schedule.daily", "Daily at 08:00")
                        : quickSetupSnapshot.schedulePreset === "weekdays"
                          ? t("watchlists:overview.onboarding.quickSetup.schedule.weekdays", "Weekdays at 08:00")
                          : t("watchlists:overview.onboarding.quickSetup.schedule.none", "Manual only")}
                  </p>
                  <p>
                    <span className="font-medium">
                      {t("watchlists:overview.onboarding.quickSetup.review.goal", "Goal")}:
                    </span>{" "}
                    {quickSetupSnapshot.setupGoal === "triage"
                      ? t("watchlists:overview.onboarding.quickSetup.goal.triage", "Feed review only")
                      : t(
                          "watchlists:overview.onboarding.quickSetup.goal.briefing",
                          "Generate briefing reports"
                        )}
                  </p>
                  <p>
                    <span className="font-medium">
                      {t("watchlists:overview.onboarding.quickSetup.review.audio", "Audio")}:
                    </span>{" "}
                    {quickSetupSnapshot.setupGoal === "triage"
                      ? t("watchlists:overview.onboarding.quickSetup.outcome.triage", "Article triage only")
                      : quickSetupSnapshot.audioBriefing
                        ? t("watchlists:overview.onboarding.quickSetup.outcome.textAndAudio", "Text + audio briefing")
                        : t("watchlists:overview.onboarding.quickSetup.outcome.textOnly", "Text briefing")}
                  </p>
                  <p>
                    <span className="font-medium">
                      {t("watchlists:overview.onboarding.quickSetup.review.runNow", "Run test now")}:
                    </span>{" "}
                    {quickSetupSnapshot.runNow
                      ? t("common:yes", "Yes")
                      : t("common:no", "No")}
                  </p>
                  <p>
                    <span className="font-medium">
                      {t("watchlists:overview.onboarding.quickSetup.review.destination", "After create")}:
                    </span>{" "}
                    {quickSetupDestinationHint}
                  </p>
                </div>

                <div className="rounded-md border border-border bg-surface p-3">
                  <div className="mb-1 flex items-center justify-between gap-2">
                    <span className="font-medium">
                      {t("watchlists:overview.onboarding.quickSetup.candidatePreview.title", "Feed sample preview")}
                    </span>
                    <Button
                      type="link"
                      size="small"
                      onClick={() => void loadQuickSetupCandidatePreview(quickSetupSnapshot)}
                    >
                      {t("watchlists:overview.onboarding.quickSetup.actions.retryPreview", "Retry preview")}
                    </Button>
                  </div>
                  <p
                    className={quickSetupCandidatePreviewError ? "text-danger" : "text-text-muted"}
                    data-testid={
                      quickSetupCandidatePreviewError
                        ? "watchlists-overview-quick-setup-candidate-error"
                        : "watchlists-overview-quick-setup-candidate-summary"
                    }
                  >
                    {quickSetupCandidateSummary}
                  </p>
                  {quickSetupCandidatePreviewLoading && (
                    <div className="mt-2">
                      <Spin size="small" />
                    </div>
                  )}
                  {!quickSetupCandidatePreviewLoading &&
                    !quickSetupCandidatePreviewError &&
                    (quickSetupCandidatePreview?.items?.length || 0) > 0 && (
                      <ul className="mt-2 space-y-1">
                        {quickSetupCandidatePreview?.items.slice(0, 4).map((item, index) => (
                          <li key={`${item.url || item.title || "candidate"}-${index}`} className="flex gap-2">
                            <Tag className="m-0" color={item.decision === "ingest" ? "green" : "red"}>
                              {item.decision}
                            </Tag>
                            <span className="text-text-muted">
                              {item.title || item.url || t("watchlists:common.unknown", "Unknown")}
                            </span>
                          </li>
                        ))}
                      </ul>
                    )}
                </div>

                <div className="rounded-md border border-border bg-surface p-3">
                  <p className="mb-2 font-medium">
                    {t(
                      "watchlists:overview.onboarding.quickSetup.templatePreview.title",
                      "Briefing preview (template: {{template}})",
                      { template: "briefing_md" }
                    )}
                  </p>
                  <pre
                    className="max-h-52 overflow-auto whitespace-pre-wrap rounded-md border border-border bg-bg p-3 text-xs leading-5 text-text"
                    data-testid="watchlists-overview-quick-setup-template-preview"
                  >
                    {quickSetupTemplatePreview}
                  </pre>
                </div>
              </div>
            )}
          </Form>
        </div>
      </Modal>
    </div>
  )
}
