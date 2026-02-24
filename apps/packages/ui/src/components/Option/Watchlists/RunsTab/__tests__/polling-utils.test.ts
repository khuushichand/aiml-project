import { describe, expect, it } from "vitest"
import { hasActiveWatchlistRuns } from "../polling-utils"

describe("hasActiveWatchlistRuns", () => {
  it("returns true when at least one run is active", () => {
    expect(
      hasActiveWatchlistRuns([
        { status: "completed" },
        { status: "pending" },
        { status: "failed" }
      ])
    ).toBe(true)

    expect(hasActiveWatchlistRuns([{ status: "RUNNING" }])).toBe(true)
  })

  it("returns false when no active runs are present", () => {
    expect(
      hasActiveWatchlistRuns([
        { status: "completed" },
        { status: "failed" },
        { status: "cancelled" }
      ])
    ).toBe(false)
  })

  it("handles nullish run records safely", () => {
    expect(
      hasActiveWatchlistRuns([null, undefined, { status: null }, { status: "" }])
    ).toBe(false)
  })
})
