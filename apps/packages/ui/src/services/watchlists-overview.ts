import {
  fetchScrapedItems,
  fetchWatchlistJobs,
  fetchWatchlistRuns,
  fetchWatchlistSources
} from "@/services/watchlists"
import type {
  PaginatedResponse,
  WatchlistJob,
  WatchlistRun,
  WatchlistSource
} from "@/types/watchlists"

const OVERVIEW_PAGE_SIZE = 200
const OVERVIEW_MAX_PAGES = 15

const HEALTHY_SOURCE_STATUSES = new Set([
  "ok",
  "healthy",
  "ready",
  "running",
  "pending",
  "queued"
])

const DEGRADED_SOURCE_STATUSES = new Set([
  "backoff",
  "deferred",
  "stale",
  "warning",
  "error",
  "failed",
  "unreachable",
  "forum_disabled"
])

export type SourceHealthBucket = "healthy" | "degraded" | "inactive" | "unknown"

export interface WatchlistsOverviewFailedRun extends WatchlistRun {
  job_name?: string
}

export interface WatchlistsOverviewData {
  fetchedAt: string
  sources: {
    total: number
    healthy: number
    degraded: number
    inactive: number
    unknown: number
  }
  jobs: {
    total: number
    active: number
    nextRunAt: string | null
  }
  items: {
    unread: number
  }
  runs: {
    running: number
    pending: number
    recentFailed: WatchlistsOverviewFailedRun[]
  }
  systemHealth: "healthy" | "degraded"
}

const normalizeStatus = (value: string | null | undefined): string =>
  String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")

const asFiniteNumber = (value: unknown, fallback = 0): number => {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : fallback
}

const parseEpochMs = (value: string | null | undefined): number | null => {
  if (!value) return null
  const parsed = Date.parse(value)
  return Number.isFinite(parsed) ? parsed : null
}

const fetchAllPages = async <T>(
  fetchPage: (params: { page: number; size: number }) => Promise<PaginatedResponse<T>>
): Promise<{ items: T[]; total: number }> => {
  let page = 1
  let total = 0
  const items: T[] = []

  while (page <= OVERVIEW_MAX_PAGES) {
    const response = await fetchPage({ page, size: OVERVIEW_PAGE_SIZE })
    const pageItems = Array.isArray(response.items) ? response.items : []
    if (page === 1) {
      total = asFiniteNumber(response.total, pageItems.length)
    }
    items.push(...pageItems)

    const reachedTotal = total > 0 && items.length >= total
    const hasMoreByFlag = response.has_more === true
    const hasMoreBySize = pageItems.length >= OVERVIEW_PAGE_SIZE
    if (!pageItems.length || reachedTotal || (!hasMoreByFlag && !hasMoreBySize)) {
      break
    }
    page += 1
  }

  return {
    items,
    total: total > 0 ? total : items.length
  }
}

export const classifySourceHealth = (source: WatchlistSource): SourceHealthBucket => {
  if (!source.active) return "inactive"
  const normalized = normalizeStatus(source.status)
  if (!normalized) return "unknown"
  if (HEALTHY_SOURCE_STATUSES.has(normalized)) return "healthy"
  if (DEGRADED_SOURCE_STATUSES.has(normalized)) return "degraded"
  return "unknown"
}

export const getEarliestNextRunAt = (
  jobs: Pick<WatchlistJob, "active" | "next_run_at">[]
): string | null => {
  let earliestMs: number | null = null
  let earliestIso: string | null = null

  jobs.forEach((job) => {
    if (!job.active || !job.next_run_at) return
    const epochMs = parseEpochMs(job.next_run_at)
    if (epochMs == null) return
    if (earliestMs == null || epochMs < earliestMs) {
      earliestMs = epochMs
      earliestIso = job.next_run_at
    }
  })

  return earliestIso
}

export const fetchWatchlistsOverviewData = async (): Promise<WatchlistsOverviewData> => {
  const [
    sourcesResult,
    jobsResult,
    unreadResult,
    runningResult,
    pendingResult,
    failedResult
  ] = await Promise.all([
    fetchAllPages((params) => fetchWatchlistSources(params)),
    fetchAllPages((params) => fetchWatchlistJobs(params)),
    fetchScrapedItems({ reviewed: false, page: 1, size: 1 }),
    fetchWatchlistRuns({ q: "running", page: 1, size: 1 }),
    fetchWatchlistRuns({ q: "pending", page: 1, size: 1 }),
    fetchWatchlistRuns({ q: "failed", page: 1, size: 5 })
  ])

  let healthy = 0
  let degraded = 0
  let inactive = 0
  let unknown = 0

  sourcesResult.items.forEach((source) => {
    const bucket = classifySourceHealth(source)
    if (bucket === "healthy") healthy += 1
    if (bucket === "degraded") degraded += 1
    if (bucket === "inactive") inactive += 1
    if (bucket === "unknown") unknown += 1
  })

  const jobs = Array.isArray(jobsResult.items) ? jobsResult.items : []
  const jobNameById = new Map<number, string>(
    jobs.map((job) => [job.id, job.name])
  )
  const activeJobs = jobs.filter((job) => job.active).length
  const recentFailed = (Array.isArray(failedResult.items) ? failedResult.items : [])
    .slice(0, 5)
    .map((run) => ({
      ...run,
      job_name: jobNameById.get(run.job_id)
    }))

  const unreadTotal = asFiniteNumber(unreadResult.total, 0)
  const runningTotal = asFiniteNumber(runningResult.total, 0)
  const pendingTotal = asFiniteNumber(pendingResult.total, 0)

  const systemHealth: "healthy" | "degraded" =
    degraded > 0 || recentFailed.length > 0 ? "degraded" : "healthy"

  return {
    fetchedAt: new Date().toISOString(),
    sources: {
      total: asFiniteNumber(sourcesResult.total, sourcesResult.items.length),
      healthy,
      degraded,
      inactive,
      unknown
    },
    jobs: {
      total: asFiniteNumber(jobsResult.total, jobs.length),
      active: activeJobs,
      nextRunAt: getEarliestNextRunAt(jobs)
    },
    items: {
      unread: unreadTotal
    },
    runs: {
      running: runningTotal,
      pending: pendingTotal,
      recentFailed
    },
    systemHealth
  }
}
