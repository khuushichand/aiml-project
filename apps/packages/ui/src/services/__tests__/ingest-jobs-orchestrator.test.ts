import { describe, expect, it, vi } from "vitest"

import {
  createIngestJobsTracker,
  pollTrackedIngestJobs
} from "@/services/tldw/ingest-jobs-orchestrator"

describe("ingest-jobs-orchestrator", () => {
  it("tracks submit payloads and cancels each batch once", async () => {
    const tracker = createIngestJobsTracker<{ label: string }>()
    tracker.trackSubmit(
      {
        batch_id: "batch-a",
        jobs: [{ id: 11 }, { id: 12 }]
      },
      { label: "first" }
    )
    tracker.trackSubmit(
      {
        batch_id: "batch-a",
        jobs: [{ id: 13 }]
      },
      { label: "second" }
    )
    tracker.trackSubmit(
      {
        batch_id: "batch-b",
        jobs: [{ id: 21 }]
      },
      { label: "third" }
    )

    const cancelled: string[] = []
    await tracker.cancelTrackedBatches(async (batchId) => {
      cancelled.push(batchId)
    })
    await tracker.cancelTrackedBatches(async (batchId) => {
      cancelled.push(batchId)
    })

    expect(tracker.getJobIds().sort((a, b) => a - b)).toEqual([11, 12, 13, 21])
    expect(cancelled.sort()).toEqual(["batch-a", "batch-b"])
  })

  it("polls tracked jobs to terminal statuses and maps results", async () => {
    const tracker = createIngestJobsTracker<{ id: string }>()
    tracker.trackSubmit(
      {
        batch_id: "batch-1",
        jobs: [{ id: 100 }, { id: 200 }]
      },
      { id: "item-1" }
    )

    const fetchCalls: number[] = []
    const fetchJob = vi
      .fn()
      .mockImplementation(async (jobId: number) => {
        fetchCalls.push(jobId)
        if (jobId === 100) {
          return {
            ok: true,
            data: { status: "completed", result: { media_id: "m1" } }
          }
        }
        return {
          ok: true,
          data: { status: "failed", error_message: "boom" }
        }
      })

    const results = await pollTrackedIngestJobs({
      tracker,
      fetchJob,
      timeoutMs: 10_000,
      pollIntervalMs: 1,
      isCancelled: () => false,
      onCancel: async () => {},
      mapCompleted: (item, data) => ({
        id: item.meta.id,
        status: "ok",
        data
      }),
      mapCancelled: (item) => ({
        id: item.meta.id,
        status: "error",
        error: "cancelled",
        data: undefined
      }),
      mapFailure: (item, details) => ({
        id: item.meta.id,
        status: "error",
        error: String(details.error || details.status || "failed"),
        data: details.data
      })
    })

    expect(fetchJob).toHaveBeenCalled()
    expect(fetchCalls).toEqual(expect.arrayContaining([100, 200]))
    expect(results).toHaveLength(2)
    expect(results[0]).toMatchObject({ status: "ok" })
    expect(results[1]).toMatchObject({ status: "error" })
  })
})
