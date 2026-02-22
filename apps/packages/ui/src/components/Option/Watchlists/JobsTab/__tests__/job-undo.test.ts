import { describe, expect, it } from "vitest"
import type { WatchlistJob } from "@/types/watchlists"
import { toJobRestoreId } from "../job-undo"

const sampleJob: WatchlistJob = {
  id: 42,
  name: "Morning Brief",
  description: "Daily digest",
  scope: {
    sources: [1, 2],
    groups: [10],
    tags: ["news"]
  },
  schedule_expr: "0 9 * * *",
  timezone: "UTC",
  active: true,
  max_concurrency: 2,
  per_host_delay_ms: 1000,
  retry_policy: { retries: 2 },
  output_prefs: { template_name: "daily-brief" },
  job_filters: { filters: [] },
  created_at: "2026-02-18T00:00:00Z",
  updated_at: "2026-02-18T00:00:00Z"
}

describe("job undo helpers", () => {
  it("maps a watchlist job into a restore id", () => {
    expect(toJobRestoreId(sampleJob)).toBe(42)
  })

  it("returns the id even when optional fields are absent", () => {
    const minimalJob = {
      ...sampleJob,
      description: null,
      schedule_expr: null,
      timezone: null,
      max_concurrency: null,
      per_host_delay_ms: null,
      retry_policy: null,
      output_prefs: null,
      job_filters: null
    } as WatchlistJob
    expect(toJobRestoreId(minimalJob)).toBe(42)
  })
})
