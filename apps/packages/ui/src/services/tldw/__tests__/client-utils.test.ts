import { describe, expect, it } from "vitest"

import { toTrimmedStringArray } from "@/services/tldw/client-utils"

describe("toTrimmedStringArray", () => {
  it("trims and filters array entries", () => {
    expect(toTrimmedStringArray([" one ", "", "two", 3, "   "])).toEqual([
      "one",
      "two"
    ])
  })

  it("normalizes a scalar string into a one-item array", () => {
    expect(toTrimmedStringArray("  single value ")).toEqual(["single value"])
    expect(toTrimmedStringArray("   ")).toEqual([])
    expect(toTrimmedStringArray(null)).toEqual([])
  })
})
