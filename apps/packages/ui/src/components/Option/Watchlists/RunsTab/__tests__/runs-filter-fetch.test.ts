import { describe, expect, it, vi } from "vitest"
import {
  fetchFilteredJobRuns,
  RUNS_CLIENT_FILTER_MAX_ITEMS
} from "../runs-filter-fetch"
import type { WatchlistRun } from "@/types/watchlists"

const buildRun = (id: number, status: WatchlistRun["status"]): WatchlistRun => ({
  id,
  job_id: 9,
  status,
  started_at: "2026-02-24T08:00:00Z",
  finished_at: null,
  stats: {},
  error_msg: null,
  log_path: null
})

describe("runs-filter-fetch", () => {
  it("fetches additional pages when first page does not satisfy filtered pagination demand", async () => {
    const fetchPage = vi
      .fn()
      .mockResolvedValueOnce({
        items: Array.from({ length: 200 }, (_unused, index) => buildRun(index + 1, "completed")),
        total: 500,
        has_more: true
      })
      .mockResolvedValueOnce({
        items: [
          ...Array.from({ length: 30 }, (_unused, index) => buildRun(1001 + index, "failed")),
          ...Array.from({ length: 170 }, (_unused, index) => buildRun(2001 + index, "completed"))
        ],
        total: 500,
        has_more: true
      })

    const result = await fetchFilteredJobRuns({
      jobId: 9,
      statusFilter: "failed",
      currentPage: 1,
      pageSize: 20,
      fetchPage
    })

    expect(fetchPage).toHaveBeenCalledTimes(2)
    expect(result.filteredItems).toHaveLength(30)
    expect(result.hasMoreInSource).toBe(true)
    expect(result.exactTotal).toBe(false)
    expect(result.truncated).toBe(false)
  })

  it("returns exact totals when source pages are exhausted", async () => {
    const fetchPage = vi.fn().mockResolvedValue({
      items: [
        ...Array.from({ length: 12 }, (_unused, index) => buildRun(index + 1, "failed")),
        ...Array.from({ length: 8 }, (_unused, index) => buildRun(101 + index, "completed"))
      ],
      total: 20,
      has_more: false
    })

    const result = await fetchFilteredJobRuns({
      jobId: 9,
      statusFilter: "failed",
      currentPage: 2,
      pageSize: 20,
      fetchPage
    })

    expect(fetchPage).toHaveBeenCalledTimes(1)
    expect(result.filteredItems).toHaveLength(12)
    expect(result.hasMoreInSource).toBe(false)
    expect(result.exactTotal).toBe(true)
    expect(result.truncated).toBe(false)
  })

  it("flags truncation when max filtered item cap is reached", async () => {
    const fetchPage = vi.fn().mockResolvedValue({
      items: Array.from({ length: 200 }, (_unused, index) => buildRun(index + 1, "failed")),
      total: 999999,
      has_more: true
    })

    const result = await fetchFilteredJobRuns({
      jobId: 9,
      statusFilter: "failed",
      currentPage: 100,
      pageSize: 100,
      fetchPage
    })

    expect(result.filteredItems.length).toBe(RUNS_CLIENT_FILTER_MAX_ITEMS)
    expect(result.hasMoreInSource).toBe(true)
    expect(result.truncated).toBe(true)
  })
})
