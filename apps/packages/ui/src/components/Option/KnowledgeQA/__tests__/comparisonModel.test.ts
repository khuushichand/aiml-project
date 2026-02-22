import { describe, expect, it } from "vitest"
import {
  createComparisonDraft,
  isComparisonReady,
  updateComparisonDraft,
} from "../comparisonModel"

describe("comparisonModel", () => {
  it("creates draft status until both queries are present", () => {
    const draft = createComparisonDraft({
      nowIso: "2026-02-18T00:00:00.000Z",
      left: { query: "Why did metric A change?" },
      right: { query: "" },
    })

    expect(draft.status).toBe("draft")
    expect(isComparisonReady(draft)).toBe(false)
  })

  it("promotes to ready when both sides have queries", () => {
    const initial = createComparisonDraft({
      nowIso: "2026-02-18T00:00:00.000Z",
      left: { query: "Question A" },
      right: { query: "" },
    })

    const updated = updateComparisonDraft(initial, {
      right: {
        query: "Question B",
        citationIndices: [2, 2, 0, 3],
      },
      nowIso: "2026-02-18T00:01:00.000Z",
    })

    expect(updated.status).toBe("ready")
    expect(isComparisonReady(updated)).toBe(true)
    expect(updated.right.citationIndices).toEqual([2, 1, 3])
    expect(updated.updatedAt).toBe("2026-02-18T00:01:00.000Z")
  })
})
