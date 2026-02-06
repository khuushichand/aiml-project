import React, { useCallback, useEffect, useRef, useState } from "react"
import {
  Button,
  Progress,
  Select,
  Space,
  Table,
  Tooltip,
  message
} from "antd"
import type { ColumnsType } from "antd/es/table"
import { Eye, RefreshCw } from "lucide-react"
import { useTranslation } from "react-i18next"
import { useWatchlistsStore } from "@/store/watchlists"
import {
  fetchJobRuns,
  exportRunsCsv,
  fetchWatchlistJobs,
  fetchWatchlistRuns
} from "@/services/watchlists"
import type { WatchlistJob, WatchlistRun } from "@/types/watchlists"
import { formatRelativeTime } from "@/utils/dateFormatters"
import { StatusTag } from "../shared"
import { RunDetailDrawer } from "./RunDetailDrawer"
import { Download } from "lucide-react"

const POLL_INTERVAL_MS = 5000
const DEFAULT_RUNS_CSV_SERVER_THRESHOLD = 2000
const RUNS_API_PAGE_SIZE = 200
const RUNS_CSV_SERVER_PAGE_SIZE = 1000

const resolveRunsCsvServerThreshold = (): number => {
  const raw = process.env.NEXT_PUBLIC_RUNS_CSV_SERVER_THRESHOLD
  if (!raw || !raw.trim()) return DEFAULT_RUNS_CSV_SERVER_THRESHOLD
  const parsed = Number(raw)
  if (!Number.isFinite(parsed) || parsed < 0) return DEFAULT_RUNS_CSV_SERVER_THRESHOLD
  return Math.floor(parsed)
}

const escapeCsvCell = (value: unknown): string => {
  const text = value == null ? "" : String(value)
  if (/[",\n]/.test(text)) {
    return `"${text.replace(/"/g, "\"\"")}"`
  }
  return text
}

const downloadCsv = (content: string, filename: string): void => {
  const blob = new Blob([content], { type: "text/csv;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  URL.revokeObjectURL(url)
}

export const RunsTab: React.FC = () => {
  const { t } = useTranslation(["watchlists", "common"])

  // Store state
  const runs = useWatchlistsStore((s) => s.runs)
  const runsLoading = useWatchlistsStore((s) => s.runsLoading)
  const runsTotal = useWatchlistsStore((s) => s.runsTotal)
  const runsPage = useWatchlistsStore((s) => s.runsPage)
  const runsPageSize = useWatchlistsStore((s) => s.runsPageSize)
  const runsJobFilter = useWatchlistsStore((s) => s.runsJobFilter)
  const runsStatusFilter = useWatchlistsStore((s) => s.runsStatusFilter)
  const pollingActive = useWatchlistsStore((s) => s.pollingActive)
  const runDetailOpen = useWatchlistsStore((s) => s.runDetailOpen)
  const selectedRunId = useWatchlistsStore((s) => s.selectedRunId)
  const [jobs, setJobs] = useState<WatchlistJob[]>([])
  const [exportingRunsCsv, setExportingRunsCsv] = useState(false)

  // Store actions
  const setRuns = useWatchlistsStore((s) => s.setRuns)
  const setRunsLoading = useWatchlistsStore((s) => s.setRunsLoading)
  const setRunsPage = useWatchlistsStore((s) => s.setRunsPage)
  const setRunsPageSize = useWatchlistsStore((s) => s.setRunsPageSize)
  const setRunsJobFilter = useWatchlistsStore((s) => s.setRunsJobFilter)
  const setRunsStatusFilter = useWatchlistsStore((s) => s.setRunsStatusFilter)
  const setPollingActive = useWatchlistsStore((s) => s.setPollingActive)
  const openRunDetail = useWatchlistsStore((s) => s.openRunDetail)
  const closeRunDetail = useWatchlistsStore((s) => s.closeRunDetail)

  // Refs for polling
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Fetch runs
  const loadRuns = useCallback(async (showLoading = true) => {
    if (showLoading) setRunsLoading(true)
    try {
      const useClientFilter = Boolean(runsJobFilter && runsStatusFilter)
      let result
      if (runsJobFilter) {
        result = await fetchJobRuns(runsJobFilter, {
          page: useClientFilter ? 1 : runsPage,
          size: useClientFilter ? 200 : runsPageSize
        })
      } else {
        result = await fetchWatchlistRuns({
          q: runsStatusFilter || undefined,
          page: runsPage,
          size: runsPageSize
        })
      }

      let items = result.items || []
      if (useClientFilter && runsStatusFilter) {
        items = items.filter((run) => run.status === runsStatusFilter)
      }

      const total = useClientFilter ? items.length : result.total
      const pagedItems = useClientFilter
        ? items.slice((runsPage - 1) * runsPageSize, runsPage * runsPageSize)
        : items

      setRuns(pagedItems, total)

      // Check if any runs are still running
      const hasRunning = items.some((r) => r.status === "running" || r.status === "pending")
      setPollingActive(hasRunning)
    } catch (err) {
      console.error("Failed to fetch runs:", err)
      if (showLoading) {
        message.error(t("watchlists:runs.fetchError", "Failed to load runs"))
      }
    } finally {
      if (showLoading) setRunsLoading(false)
    }
  }, [
    runsJobFilter,
    runsStatusFilter,
    runsPage,
    runsPageSize,
    setRuns,
    setRunsLoading,
    setPollingActive,
    t
  ])

  // Load jobs for filter dropdown
  const loadJobs = useCallback(async () => {
    try {
      const result = await fetchWatchlistJobs({ page: 1, size: 200 })
      setJobs(result.items || [])
    } catch (err) {
      console.error("Failed to fetch jobs:", err)
    }
  }, [])

  // Initial load
  useEffect(() => {
    loadRuns()
    loadJobs()
  }, [loadRuns, loadJobs])

  // Polling for active runs
  useEffect(() => {
    if (pollingActive) {
      pollIntervalRef.current = setInterval(() => {
        loadRuns(false)
      }, POLL_INTERVAL_MS)
    } else if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current)
      pollIntervalRef.current = null
    }

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
      }
    }
  }, [pollingActive, loadRuns])

  // Get job name by ID
  const getJobName = useCallback(
    (jobId: number) => {
      const job = jobs.find((j) => j.id === jobId)
      return job?.name || `Job #${jobId}`
    },
    [jobs]
  )

  // Calculate duration
  const calculateDuration = (run: WatchlistRun): string => {
    if (!run.started_at) return "-"
    const start = new Date(run.started_at)
    const end = run.finished_at ? new Date(run.finished_at) : new Date()
    const durationMs = end.getTime() - start.getTime()

    if (durationMs < 1000) return "<1s"
    if (durationMs < 60000) return `${Math.round(durationMs / 1000)}s`
    if (durationMs < 3600000) return `${Math.round(durationMs / 60000)}m`
    return `${Math.round(durationMs / 3600000)}h`
  }

  const fetchAllRunsForClientCsv = useCallback(async (): Promise<WatchlistRun[]> => {
    const useClientFilter = Boolean(runsJobFilter && runsStatusFilter)
    let page = 1
    const collected: WatchlistRun[] = []
    let hasMore = true
    while (hasMore) {
      const result = runsJobFilter
        ? await fetchJobRuns(runsJobFilter, { page, size: RUNS_API_PAGE_SIZE })
        : await fetchWatchlistRuns({
            q: runsStatusFilter || undefined,
            page,
            size: RUNS_API_PAGE_SIZE
          })
      const items = Array.isArray(result.items) ? result.items : []
      if (!items.length) break
      collected.push(...items)
      if (typeof result.has_more === "boolean") {
        hasMore = result.has_more
      } else {
        hasMore = items.length >= RUNS_API_PAGE_SIZE
      }
      page += 1
    }
    if (useClientFilter && runsStatusFilter) {
      return collected.filter((run) => run.status === runsStatusFilter)
    }
    return collected
  }, [runsJobFilter, runsStatusFilter])

  const toRunsCsv = useCallback((items: WatchlistRun[]): string => {
    const rows = [
      [
        "id",
        "job_id",
        "status",
        "started_at",
        "finished_at",
        "items_found",
        "items_ingested",
        "items_filtered",
        "items_duplicates",
        "items_errored",
        "filters_include",
        "filters_exclude",
        "filters_flag"
      ].join(",")
    ]
    items.forEach((run) => {
      const stats = run.stats || {}
      const filtersActionsRaw = (stats as Record<string, unknown>)?.filters_actions
      const filtersActions =
        filtersActionsRaw && typeof filtersActionsRaw === "object"
          ? (filtersActionsRaw as Record<string, number>)
          : {}
      rows.push(
        [
          run.id,
          run.job_id,
          run.status,
          run.started_at || "",
          run.finished_at || "",
          stats?.items_found ?? 0,
          stats?.items_ingested ?? 0,
          stats?.items_filtered ?? 0,
          stats?.items_duplicates ?? stats?.items_duplicate ?? 0,
          stats?.items_errored ?? 0,
          filtersActions.include ?? 0,
          filtersActions.exclude ?? 0,
          filtersActions.flag ?? 0
        ]
          .map(escapeCsvCell)
          .join(",")
      )
    })
    return `${rows.join("\n")}\n`
  }, [])

  const fetchServerRunsCsvMerged = useCallback(async (): Promise<string> => {
    const scope: "global" | "job" = runsJobFilter ? "job" : "global"
    const q = !runsJobFilter && runsStatusFilter ? runsStatusFilter : undefined
    let page = 1
    let header = ""
    const dataRows: string[] = []

    // Merge paginated CSV chunks into a single downloadable CSV.
    while (true) {
      const csvChunk = await exportRunsCsv({
        scope,
        job_id: runsJobFilter || undefined,
        q,
        page,
        size: RUNS_CSV_SERVER_PAGE_SIZE,
        include_tallies: false
      })
      const lines = csvChunk.split("\n")
      if (!header) {
        header = lines[0] || ""
      }
      const rows = lines.slice(1).filter((line) => line.trim().length > 0)
      if (!rows.length) break
      const filteredRows =
        runsJobFilter && runsStatusFilter
          ? rows.filter((line) => {
              const cols = line.split(",")
              return (cols[2] || "").trim().toLowerCase() === runsStatusFilter.toLowerCase()
            })
          : rows
      dataRows.push(...filteredRows)
      if (rows.length < RUNS_CSV_SERVER_PAGE_SIZE) break
      page += 1
      if (page > 200) break
    }
    if (!header) return ""
    return `${[header, ...dataRows].join("\n")}\n`
  }, [runsJobFilter, runsStatusFilter])

  const handleExportRunsCsv = useCallback(async () => {
    try {
      setExportingRunsCsv(true)
      const threshold = resolveRunsCsvServerThreshold()
      const rowEstimate = Math.max(Number(runsTotal || 0), Array.isArray(runs) ? runs.length : 0)
      const preferServerCsv = rowEstimate >= threshold
      const csv = preferServerCsv
        ? await fetchServerRunsCsvMerged()
        : toRunsCsv(await fetchAllRunsForClientCsv())
      if (!csv || !csv.trim()) {
        message.warning(t("watchlists:runs.exportEmpty", "No runs available to export"))
        return
      }
      const filenameSuffix = runsJobFilter ? `job_${runsJobFilter}` : "global"
      const filename = `watchlists_runs_${filenameSuffix}_${Date.now()}.csv`
      downloadCsv(csv, filename)
      message.success(t("watchlists:runs.exported", "Runs CSV exported"))
    } catch (err) {
      console.error("Failed to export runs CSV:", err)
      message.error(t("watchlists:runs.exportError", "Failed to export runs CSV"))
    } finally {
      setExportingRunsCsv(false)
    }
  }, [
    fetchAllRunsForClientCsv,
    fetchServerRunsCsvMerged,
    runs,
    runsJobFilter,
    runsTotal,
    t,
    toRunsCsv
  ])

  // Table columns
  const columns: ColumnsType<WatchlistRun> = [
    {
      title: t("watchlists:runs.columns.job", "Job"),
      key: "job",
      width: 200,
      ellipsis: true,
      render: (_, record) => (
        <span className="font-medium">{getJobName(record.job_id)}</span>
      )
    },
    {
      title: t("watchlists:runs.columns.status", "Status"),
      dataIndex: "status",
      key: "status",
      width: 120,
      render: (status: string, record) => (
        <div className="flex items-center gap-2">
          <StatusTag status={status} />
          {status === "running" && (
            <Progress
              percent={Math.round(
                ((record.stats?.items_ingested || 0) /
                  Math.max(record.stats?.items_found || 1, 1)) *
                  100
              )}
              size="small"
              showInfo={false}
              className="w-16"
            />
          )}
        </div>
      )
    },
    {
      title: t("watchlists:runs.columns.started", "Started"),
      dataIndex: "started_at",
      key: "started_at",
      width: 140,
      render: (date: string | null) =>
        date ? (
          <span className="text-sm text-zinc-500">
            {formatRelativeTime(date, t)}
          </span>
        ) : (
          <span className="text-sm text-zinc-400">-</span>
        )
    },
    {
      title: t("watchlists:runs.columns.duration", "Duration"),
      key: "duration",
      width: 80,
      render: (_, record) => (
        <span className="text-sm text-zinc-600 dark:text-zinc-400">
          {calculateDuration(record)}
        </span>
      )
    },
    {
      title: t("watchlists:runs.columns.itemsFound", "Found"),
      key: "items_found",
      width: 80,
      align: "center",
      render: (_, record) => (
        <span className="text-sm">
          {record.stats?.items_found ?? "-"}
        </span>
      )
    },
    {
      title: t("watchlists:runs.columns.itemsProcessed", "Processed"),
      key: "items_processed",
      width: 100,
      align: "center",
      render: (_, record) => (
        <span className="text-sm">
          {record.stats?.items_ingested ?? "-"}
        </span>
      )
    },
    {
      title: t("watchlists:runs.columns.itemsFiltered", "Filtered"),
      key: "items_filtered",
      width: 100,
      align: "center",
      render: (_, record) => (
        <span className="text-sm">
          {record.stats?.items_filtered ?? "-"}
        </span>
      )
    },
    {
      title: t("watchlists:runs.columns.itemsErrored", "Errors"),
      key: "items_errored",
      width: 90,
      align: "center",
      render: (_, record) => (
        <span className="text-sm">
          {record.stats?.items_errored ?? "-"}
        </span>
      )
    },
    {
      title: t("watchlists:runs.columns.actions", "Actions"),
      key: "actions",
      width: 80,
      align: "center",
      render: (_, record) => (
        <Tooltip title={t("watchlists:runs.viewDetails", "View Details")}>
          <Button
            type="text"
            size="small"
            icon={<Eye className="h-4 w-4" />}
            onClick={() => openRunDetail(record.id)}
          />
        </Tooltip>
      )
    }
  ]

  // Status options for filter
  const statusOptions = [
    { value: "pending", label: "Pending" },
    { value: "running", label: "Running" },
    { value: "completed", label: "Completed" },
    { value: "failed", label: "Failed" },
    { value: "cancelled", label: "Cancelled" }
  ]

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-3">
          <Select
            placeholder={t("watchlists:runs.filterByJob", "Filter by job")}
            value={runsJobFilter}
            onChange={setRunsJobFilter}
            allowClear
            className="w-48"
            options={jobs.map((j) => ({
              label: j.name,
              value: j.id
            }))}
          />
          <Select
            placeholder={t("watchlists:runs.filterByStatus", "Filter by status")}
            value={runsStatusFilter}
            onChange={setRunsStatusFilter}
            allowClear
            className="w-36"
            options={statusOptions}
          />
        </div>
        <div className="flex items-center gap-2">
          {pollingActive && (
            <span className="text-sm text-blue-500 flex items-center gap-1">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500" />
              </span>
              Auto-refreshing
            </span>
          )}
          <Button
            icon={<RefreshCw className="h-4 w-4" />}
            onClick={() => loadRuns()}
            loading={runsLoading}
          >
            {t("common:refresh", "Refresh")}
          </Button>
          <Button
            icon={<Download className="h-4 w-4" />}
            onClick={handleExportRunsCsv}
            loading={exportingRunsCsv}
          >
            {t("watchlists:runs.exportCsv", "Export CSV")}
          </Button>
        </div>
      </div>

      {/* Description */}
      <div className="text-sm text-zinc-500">
        {t("watchlists:runs.description", "View execution history and logs for your watchlist jobs.")}
      </div>

      {/* Table */}
      <Table
        dataSource={Array.isArray(runs) ? runs : []}
        columns={columns}
        rowKey="id"
        loading={runsLoading}
        pagination={{
          current: runsPage,
          pageSize: runsPageSize,
          total: runsTotal,
          showSizeChanger: true,
          showTotal: (total) =>
            t("watchlists:runs.totalItems", "{{total}} runs", { total }),
          onChange: (page, pageSize) => {
            setRunsPage(page)
            if (pageSize !== runsPageSize) {
              setRunsPageSize(pageSize)
            }
          }
        }}
        size="middle"
        scroll={{ x: 800 }}
      />

      {/* Run Detail Drawer */}
      <RunDetailDrawer
        runId={selectedRunId}
        open={runDetailOpen}
        onClose={closeRunDetail}
      />
    </div>
  )
}
