import React, { useCallback, useEffect, useRef, useState } from "react"
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
  triggerWatchlistRun
} from "@/services/watchlists"
import {
  fetchWatchlistsOverviewData,
  type WatchlistsOverviewData
} from "@/services/watchlists-overview"
import { formatRelativeTime } from "@/utils/dateFormatters"
import {
  QUICK_SETUP_DEFAULT_VALUES,
  type QuickSetupValues,
  toQuickSetupJobPayload,
  toQuickSetupSourcePayload
} from "./quick-setup"

const OVERVIEW_REFRESH_INTERVAL_MS = 30_000
const QUICK_SETUP_MAX_STEP = 2
const QUICK_SETUP_STEP_FIELDS: Array<Array<keyof QuickSetupValues>> = [
  ["sourceName", "sourceUrl", "sourceType"],
  ["monitorName", "schedulePreset", "runNow"],
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
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const [quickSetupForm] = Form.useForm<QuickSetupValues>()

  const setActiveTab = useWatchlistsStore((s) => s.setActiveTab)
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
      setError(null)
    } catch (err) {
      console.error("Failed to load watchlists overview:", err)
      setError(t("watchlists:overview.fetchError", "Failed to load overview"))
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [t])

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

  const openQuickSetup = useCallback(() => {
    quickSetupForm.setFieldsValue(QUICK_SETUP_DEFAULT_VALUES)
    setQuickSetupStep(0)
    setQuickSetupOpen(true)
  }, [quickSetupForm])

  const closeQuickSetup = useCallback(() => {
    setQuickSetupOpen(false)
    setQuickSetupStep(0)
    quickSetupForm.resetFields()
  }, [quickSetupForm])

  const handleQuickSetupNext = useCallback(async () => {
    const fields = QUICK_SETUP_STEP_FIELDS[quickSetupStep] || []
    if (fields.length > 0) {
      await quickSetupForm.validateFields(fields)
    }
    if (quickSetupStep === 0) {
      const sourceName = String(quickSetupForm.getFieldValue("sourceName") || "").trim()
      const monitorName = String(quickSetupForm.getFieldValue("monitorName") || "").trim()
      if (sourceName.length > 0 && monitorName.length === 0) {
        quickSetupForm.setFieldsValue({
          monitorName: `${sourceName} Monitor`
        })
      }
    }
    setQuickSetupStep((prev) => Math.min(prev + 1, QUICK_SETUP_MAX_STEP))
  }, [quickSetupForm, quickSetupStep, t])

  const handleQuickSetupBack = useCallback(() => {
    setQuickSetupStep((prev) => Math.max(prev - 1, 0))
  }, [])

  const completeQuickSetup = useCallback(async () => {
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
        const run = await triggerWatchlistRun(job.id)
        runId = run.id
      }

      message.success(
        values.runNow
          ? t(
              "watchlists:overview.onboarding.quickSetup.createdAndRunning",
              "Quick setup complete. Your first run has started."
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
      } else {
        setActiveTab("jobs")
      }
    } catch (err) {
      console.error("Failed to complete quick setup:", err)
      message.error(
        t(
          "watchlists:overview.onboarding.quickSetup.error",
          "Failed to complete quick setup."
        )
      )
    } finally {
      setQuickSetupSubmitting(false)
    }
  }, [closeQuickSetup, loadOverview, openRunDetail, quickSetupForm, setActiveTab, t])

  const quickSetupValues = Form.useWatch([], quickSetupForm) as Partial<QuickSetupValues> | undefined
  const quickSetupIsLastStep = quickSetupStep >= QUICK_SETUP_MAX_STEP

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
                  {t("watchlists:overview.cards.runs.title", "Run Queue")}
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
        onCancel={quickSetupSubmitting ? undefined : closeQuickSetup}
        destroyOnHidden
        maskClosable={!quickSetupSubmitting}
        footer={[
          <Button
            key="cancel"
            onClick={closeQuickSetup}
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
              ? t("watchlists:overview.onboarding.quickSetup.actions.finish", "Create setup")
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
                  label={t("watchlists:overview.onboarding.quickSetup.fields.runNow", "Run immediately")}
                  name="runNow"
                  valuePropName="checked"
                >
                  <Switch />
                </Form.Item>
              </div>
            )}

            {quickSetupStep === 2 && (
              <div className="space-y-3 text-sm">
                <p className="text-text-muted">
                  {t(
                    "watchlists:overview.onboarding.quickSetup.reviewDescription",
                    "Confirm your setup, then create your feed and monitor."
                  )}
                </p>
                <div className="rounded-md border border-border bg-surface p-3">
                  <p>
                    <span className="font-medium">
                      {t("watchlists:overview.onboarding.quickSetup.review.feed", "Feed")}:
                    </span>{" "}
                    {quickSetupValues?.sourceName || "—"}
                  </p>
                  <p className="text-text-muted">
                    {quickSetupValues?.sourceUrl || "—"}
                  </p>
                  <p className="mt-2">
                    <span className="font-medium">
                      {t("watchlists:overview.onboarding.quickSetup.review.monitor", "Monitor")}:
                    </span>{" "}
                    {quickSetupValues?.monitorName || "—"}
                  </p>
                  <p>
                    <span className="font-medium">
                      {t("watchlists:overview.onboarding.quickSetup.review.schedule", "Schedule")}:
                    </span>{" "}
                    {quickSetupValues?.schedulePreset === "hourly"
                      ? t("watchlists:overview.onboarding.quickSetup.schedule.hourly", "Hourly")
                      : quickSetupValues?.schedulePreset === "daily"
                        ? t("watchlists:overview.onboarding.quickSetup.schedule.daily", "Daily at 08:00")
                        : quickSetupValues?.schedulePreset === "weekdays"
                          ? t("watchlists:overview.onboarding.quickSetup.schedule.weekdays", "Weekdays at 08:00")
                          : t("watchlists:overview.onboarding.quickSetup.schedule.none", "Manual only")}
                  </p>
                  <p>
                    <span className="font-medium">
                      {t("watchlists:overview.onboarding.quickSetup.review.runNow", "Run now")}:
                    </span>{" "}
                    {quickSetupValues?.runNow
                      ? t("common:yes", "Yes")
                      : t("common:no", "No")}
                  </p>
                </div>
              </div>
            )}
          </Form>
        </div>
      </Modal>
    </div>
  )
}
