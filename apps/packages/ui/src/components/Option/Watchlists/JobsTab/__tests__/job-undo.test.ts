import { describe, expect, it } from "vitest"
import type { WatchlistJob } from "@/types/watchlists"
import { toJobCreatePayload } from "../job-undo"

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
  it("maps a watchlist job into a create payload for restore", () => {
    expect(toJobCreatePayload(sampleJob)).toEqual({
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
      job_filters: { filters: [] }
    })
  })

  it("keeps optional fields undefined when absent", () => {
    const minimalPayload = toJobCreatePayload({
      ...sampleJob,
      description: null,
      schedule_expr: null,
      timezone: null,
      max_concurrency: null,
      per_host_delay_ms: null,
      retry_policy: null,
      output_prefs: null,
      job_filters: null
    })

    expect(minimalPayload).toMatchObject({
      name: "Morning Brief",
      scope: {
        sources: [1, 2],
        groups: [10],
        tags: ["news"]
      },
      active: true
    })
    expect(minimalPayload.description).toBeUndefined()
    expect(minimalPayload.schedule_expr).toBeUndefined()
    expect(minimalPayload.timezone).toBeUndefined()
    expect(minimalPayload.max_concurrency).toBeUndefined()
    expect(minimalPayload.per_host_delay_ms).toBeUndefined()
    expect(minimalPayload.retry_policy).toBeUndefined()
    expect(minimalPayload.output_prefs).toBeUndefined()
    expect(minimalPayload.job_filters).toBeUndefined()
  })
})
