import { describe, expect, it } from "vitest"
import { buildBulkCountSummary, collectFailedIds } from "../bulk-result-utils"

describe("bulk-result-utils", () => {
  it("collects failed ids from Promise.allSettled results", () => {
    const ids = ["a", "b", "c", "d"]
    const results: PromiseSettledResult<unknown>[] = [
      { status: "fulfilled", value: "ok-a" },
      { status: "rejected", reason: new Error("fail-b") },
      { status: "fulfilled", value: "ok-c" },
      { status: "rejected", reason: new Error("fail-d") }
    ]

    expect(collectFailedIds(ids, results)).toEqual(["b", "d"])
  })

  it("builds success/failure summary counts safely", () => {
    expect(buildBulkCountSummary(10, 3)).toEqual({
      total: 10,
      succeeded: 7,
      failed: 3
    })

    expect(buildBulkCountSummary(-4, -2)).toEqual({
      total: 0,
      succeeded: 0,
      failed: 0
    })
  })
})
