import { describe, expect, it } from "vitest"
import {
  normalizeSourceIds,
  resolveCheckNowTargets,
  shouldConfirmMultiSourceCheck
} from "../check-now-utils"

describe("check-now utils", () => {
  it("normalizes and deduplicates valid positive integer IDs", () => {
    expect(normalizeSourceIds([1, 2, 2, "3", 0, -1, null, undefined, "abc"])).toEqual([1, 2, 3])
  })

  it("uses selected sources when clicking a selected row with multi-selection", () => {
    expect(resolveCheckNowTargets(2, [1, 2, 3])).toEqual([1, 2, 3])
  })

  it("falls back to clicked source when clicked row is outside the multi-selection", () => {
    expect(resolveCheckNowTargets(4, [1, 2, 3])).toEqual([4])
  })

  it("requires confirmation only for multi-source checks", () => {
    expect(shouldConfirmMultiSourceCheck([1])).toBe(false)
    expect(shouldConfirmMultiSourceCheck([1, 2])).toBe(true)
  })
})
