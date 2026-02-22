import { describe, expect, it } from "vitest"
import { countToggleImpact, summarizeSourceSelection } from "../bulk-action-summary"

describe("bulk action summary", () => {
  const selected = [
    { active: true, source_type: "rss" as const },
    { active: false, source_type: "site" as const },
    { active: false, source_type: "rss" as const },
    { active: true, source_type: "forum" as const }
  ]

  it("summarizes selected feed counts", () => {
    const summary = summarizeSourceSelection(selected)
    expect(summary).toEqual({
      total: 4,
      active: 2,
      inactive: 2,
      byType: {
        rss: 2,
        site: 1,
        forum: 1
      }
    })
  })

  it("counts toggle impact for enable and disable operations", () => {
    expect(countToggleImpact(selected, true)).toBe(2)
    expect(countToggleImpact(selected, false)).toBe(2)
  })
})
