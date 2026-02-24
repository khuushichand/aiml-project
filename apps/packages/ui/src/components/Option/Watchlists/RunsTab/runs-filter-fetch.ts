import type { WatchlistRun } from "@/types/watchlists"

export const RUNS_CLIENT_FILTER_PAGE_SIZE = 200
export const RUNS_CLIENT_FILTER_MAX_ITEMS = 5000
export const RUNS_CLIENT_FILTER_MAX_PAGES = 25

export interface JobRunsPageResponse {
  items?: WatchlistRun[]
  total?: number
  has_more?: boolean
}

export type JobRunsPageFetcher = (
  jobId: number,
  params: { page: number; size: number }
) => Promise<JobRunsPageResponse>

export interface FetchFilteredJobRunsParams {
  jobId: number
  statusFilter: string
  currentPage: number
  pageSize: number
  fetchPage: JobRunsPageFetcher
}

export interface FetchFilteredJobRunsResult {
  filteredItems: WatchlistRun[]
  hasMoreInSource: boolean
  exactTotal: boolean
  truncated: boolean
}

const normalizeStatus = (value: unknown): string =>
  String(value || "").trim().toLowerCase()

export const fetchFilteredJobRuns = async ({
  jobId,
  statusFilter,
  currentPage,
  pageSize,
  fetchPage
}: FetchFilteredJobRunsParams): Promise<FetchFilteredJobRunsResult> => {
  const filteredItems: WatchlistRun[] = []
  const normalizedStatus = normalizeStatus(statusFilter)
  const desiredCount = Math.max(1, currentPage) * Math.max(1, pageSize)

  let page = 1
  let hasMoreInSource = false
  let exactTotal = false
  let truncated = false

  while (page <= RUNS_CLIENT_FILTER_MAX_PAGES) {
    const response = await fetchPage(jobId, {
      page,
      size: RUNS_CLIENT_FILTER_PAGE_SIZE
    })
    const batch = Array.isArray(response.items) ? response.items : []
    const hasMoreFlag = response.has_more === true
    const total = Number(response.total || 0)
    const reachedKnownEnd = total > 0 && page * RUNS_CLIENT_FILTER_PAGE_SIZE >= total
    const reachedBatchEnd = batch.length < RUNS_CLIENT_FILTER_PAGE_SIZE
    const noMoreSource = !hasMoreFlag && (reachedBatchEnd || reachedKnownEnd)

    for (const run of batch) {
      if (normalizeStatus(run.status) === normalizedStatus) {
        filteredItems.push(run)
      }
      if (filteredItems.length >= RUNS_CLIENT_FILTER_MAX_ITEMS) {
        truncated = true
        break
      }
    }

    if (truncated) {
      hasMoreInSource = true
      break
    }

    if (noMoreSource) {
      hasMoreInSource = false
      exactTotal = true
      break
    }

    if (filteredItems.length >= desiredCount) {
      hasMoreInSource = true
      exactTotal = false
      break
    }

    page += 1
  }

  if (page > RUNS_CLIENT_FILTER_MAX_PAGES) {
    truncated = true
    hasMoreInSource = true
  }

  return {
    filteredItems,
    hasMoreInSource,
    exactTotal,
    truncated
  }
}
