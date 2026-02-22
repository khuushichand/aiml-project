import { beforeEach, describe, expect, it } from "vitest"
import {
  createInitialQuickIngestLastRunSummary,
  useQuickIngestStore
} from "../quick-ingest"

describe("quick ingest store", () => {
  beforeEach(() => {
    useQuickIngestStore.setState((prev) => ({
      ...prev,
      queuedCount: 0,
      hadRecentFailure: false,
      lastRunSummary: createInitialQuickIngestLastRunSummary()
    }))
  })

  it("records success run summary", () => {
    useQuickIngestStore.getState().recordRunSuccess({
      totalCount: 3,
      successCount: 2,
      failedCount: 1,
      firstMediaId: 1234,
      primarySourceLabel: "https://example.com/source"
    })

    const summary = useQuickIngestStore.getState().lastRunSummary
    expect(summary.status).toBe("success")
    expect(summary.totalCount).toBe(3)
    expect(summary.successCount).toBe(2)
    expect(summary.failedCount).toBe(1)
    expect(summary.firstMediaId).toBe("1234")
    expect(summary.primarySourceLabel).toBe("https://example.com/source")
    expect(summary.errorMessage).toBeNull()
    expect(summary.completedAt).toBeTypeOf("number")
  })

  it("records failure run summary with defaults", () => {
    useQuickIngestStore.getState().recordRunFailure({
      errorMessage: "Invalid API key"
    })

    const summary = useQuickIngestStore.getState().lastRunSummary
    expect(summary.status).toBe("error")
    expect(summary.totalCount).toBe(0)
    expect(summary.successCount).toBe(0)
    expect(summary.failedCount).toBe(1)
    expect(summary.errorMessage).toBe("Invalid API key")
  })

  it("resets run summary", () => {
    useQuickIngestStore.getState().recordRunSuccess({
      totalCount: 1,
      successCount: 1,
      failedCount: 0,
      firstMediaId: "abc"
    })
    useQuickIngestStore.getState().resetLastRunSummary()

    const summary = useQuickIngestStore.getState().lastRunSummary
    expect(summary).toEqual(createInitialQuickIngestLastRunSummary())
  })
})
