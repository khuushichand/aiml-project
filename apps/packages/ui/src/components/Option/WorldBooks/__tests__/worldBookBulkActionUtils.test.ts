import { describe, expect, it } from "vitest"
import {
  buildBulkSetPriorityPayload,
  clampBulkPriority,
  normalizeBulkEntryIds
} from "../worldBookBulkActionUtils"

describe("worldBookBulkActionUtils", () => {
  it("clamps priority values to the 0-100 range", () => {
    expect(clampBulkPriority(120)).toBe(100)
    expect(clampBulkPriority(-5)).toBe(0)
    expect(clampBulkPriority(49.7)).toBe(50)
    expect(clampBulkPriority("not-a-number")).toBe(50)
  })

  it("normalizes entry ids from mixed input", () => {
    expect(normalizeBulkEntryIds([1, "2", "x", 0, -1])).toEqual([1, 2])
    expect(normalizeBulkEntryIds(null)).toEqual([])
  })

  it("builds a set-priority payload with normalized ids and clamped priority", () => {
    expect(buildBulkSetPriorityPayload(["1", 2, "bad"], 145)).toEqual({
      entry_ids: [1, 2],
      operation: "set_priority",
      priority: 100
    })
  })
})
