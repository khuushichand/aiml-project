import { describe, expect, it } from "vitest"
import { findActiveSourceUsage, mapActiveSourceUsage } from "../source-usage"

describe("source usage dependency checks", () => {
  it("returns active monitors that directly reference a feed", () => {
    const usage = findActiveSourceUsage(
      [
        {
          id: 1,
          name: "Daily Monitor",
          active: true,
          scope: { sources: [11, 22] }
        },
        {
          id: 2,
          name: "Inactive Monitor",
          active: false,
          scope: { sources: [11] }
        }
      ] as any,
      11
    )

    expect(usage).toEqual([{ id: 1, name: "Daily Monitor" }])
  })

  it("maps usage for multiple feeds in a single pass", () => {
    const usageMap = mapActiveSourceUsage(
      [
        {
          id: 10,
          name: "Morning Brief",
          active: true,
          scope: { sources: [1, 2] }
        },
        {
          id: 11,
          name: "Evening Brief",
          active: true,
          scope: { sources: [2] }
        }
      ] as any,
      [1, 2, 3]
    )

    expect(usageMap.get(1)).toEqual([{ id: 10, name: "Morning Brief" }])
    expect(usageMap.get(2)).toEqual([
      { id: 10, name: "Morning Brief" },
      { id: 11, name: "Evening Brief" }
    ])
    expect(usageMap.get(3)).toEqual([])
  })
})
