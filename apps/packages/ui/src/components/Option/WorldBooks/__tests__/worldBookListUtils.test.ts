import { describe, expect, it } from "vitest"
import {
  formatWorldBookLastModified,
  parseWorldBookTimestamp,
  UNKNOWN_LAST_MODIFIED_LABEL
} from "../worldBookListUtils"

describe("worldBookListUtils", () => {
  it("parses string and second-based numeric timestamps", () => {
    expect(parseWorldBookTimestamp("2026-02-18T09:00:00Z")).toBe(1771405200000)
    expect(parseWorldBookTimestamp(1771405200)).toBe(1771405200000)
  })

  it("returns unknown-safe display values for null/invalid timestamps", () => {
    expect(parseWorldBookTimestamp("invalid-date")).toBeNull()
    expect(formatWorldBookLastModified(null)).toEqual({
      relative: UNKNOWN_LAST_MODIFIED_LABEL,
      absolute: null,
      timestamp: null
    })
  })

  it("formats relative and absolute timestamps from a stable now", () => {
    const nowMs = Date.parse("2026-02-18T12:00:00Z")
    expect(
      formatWorldBookLastModified("2026-02-18T09:00:00Z", { nowMs })
    ).toEqual({
      relative: "3 hours ago",
      absolute: "2026-02-18 09:00:00 UTC",
      timestamp: 1771405200000
    })
  })
})
