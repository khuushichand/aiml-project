import { describe, expect, it } from "vitest"
import { computeResponseDiffPreview } from "../compare-response-diff"

describe("compare-response-diff", () => {
  it("returns added and removed highlights between candidate and baseline", () => {
    const diff = computeResponseDiffPreview({
      baseline: "Alpha leads. Beta follows.",
      candidate: "Alpha leads. Gamma arrives.",
      maxHighlights: 3
    })

    expect(diff.baselineSegments).toBe(2)
    expect(diff.candidateSegments).toBe(2)
    expect(diff.sharedSegments).toBe(1)
    expect(diff.overlapRatio).toBe(0.5)
    expect(diff.addedHighlights).toEqual(["Gamma arrives."])
    expect(diff.removedHighlights).toEqual(["Beta follows."])
    expect(diff.hasMeaningfulDifference).toBe(true)
  })

  it("normalizes whitespace and casing so equivalent responses are not flagged", () => {
    const diff = computeResponseDiffPreview({
      baseline: "Hello   world!   Next step?",
      candidate: "hello world! next step?"
    })

    expect(diff.sharedSegments).toBe(2)
    expect(diff.overlapRatio).toBe(1)
    expect(diff.addedHighlights).toEqual([])
    expect(diff.removedHighlights).toEqual([])
    expect(diff.hasMeaningfulDifference).toBe(false)
  })

  it("limits highlight counts and handles empty candidate text", () => {
    const diff = computeResponseDiffPreview({
      baseline: "One. Two. Three.",
      candidate: "",
      maxHighlights: 1
    })

    expect(diff.candidateSegments).toBe(0)
    expect(diff.addedHighlights).toEqual([])
    expect(diff.removedHighlights).toEqual(["One."])
    expect(diff.overlapRatio).toBe(0)
  })
})
