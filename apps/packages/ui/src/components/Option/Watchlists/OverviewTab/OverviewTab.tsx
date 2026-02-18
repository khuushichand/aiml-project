import React, { useCallback, useEffect, useRef, useState } from "react"
import {
  Alert,
  Button,
  Card,
  Empty,
  List,
  Space,
  Steps,
  Spin,
  Statistic,
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
  fetchWatchlistsOverviewData,
  type WatchlistsOverviewData
} from "@/services/watchlists-overview"
import { formatRelativeTime } from "@/utils/dateFormatters"

const OVERVIEW_REFRESH_INTERVAL_MS = 30_000

export const OverviewTab: React.FC = () => {
  const { t } = useTranslation(["watchlists", "common"])
  const [data, setData] = useState<WatchlistsOverviewData | null>(null)
  const [loading, setLoading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const setActiveTab = useWatchlistsStore((s) => s.setActiveTab)
  const openRunDetail = useWatchlistsStore((s) => s.openRunDetail)

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

  const handleOpenRuns = useCallback(() => {
    setActiveTab("runs")
  }, [setActiveTab])

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
        <Alert type="error" showIcon message={error} />
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
                    description: t(
                      "watchlists:overview.onboarding.steps.addFeed.description",
                      "Start by adding an RSS/site source in Feeds."
                    )
                  },
                  {
                    title: t("watchlists:overview.onboarding.steps.createMonitor.title", "Create your first monitor"),
                    description: t(
                      "watchlists:overview.onboarding.steps.createMonitor.description",
                      "Pick feeds, then set a schedule with presets."
                    )
                  },
                  {
                    title: t("watchlists:overview.onboarding.steps.reviewResults.title", "Review results"),
                    description: t(
                      "watchlists:overview.onboarding.steps.reviewResults.description",
                      "Open Articles for content and Activity for run diagnostics."
                    )
                  }
                ]}
              />
              <Space className="mt-4" wrap>
                {data.sources.total === 0 && (
                  <Button type="primary" onClick={handleOpenSources}>
                    {t("watchlists:overview.onboarding.cta.addFeed", "Add first feed")}
                  </Button>
                )}
                {data.sources.total > 0 && data.jobs.total === 0 && (
                  <Button type="primary" onClick={handleOpenJobs}>
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
            message={
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
              message={t("watchlists:overview.setupComplete.title", "Setup complete")}
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
                              t("watchlists:overview.failedRuns.jobFallback", "Job #{{id}}", {
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
    </div>
  )
}
