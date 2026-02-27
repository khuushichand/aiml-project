import { describe, expect, it } from "vitest"
import {
  buildTokenPreviewRows,
  normalizeTokenPreviewText
} from "../writing-token-utils"

describe("writing token utils", () => {
  it("normalizes control characters for preview", () => {
    expect(normalizeTokenPreviewText("a\nb\rc\t")).toBe("a\\nb\\rc\\t")
  })

  it("builds token rows with optional strings", () => {
    const rows = buildTokenPreviewRows([10, 11, 12], ["foo", "\n", "bar"])
    expect(rows).toEqual([
      { index: 0, id: 10, text: "foo" },
      { index: 1, id: 11, text: "\\n" },
      { index: 2, id: 12, text: "bar" }
    ])
  })

  it("truncates rows to maxRows and handles missing strings", () => {
    const rows = buildTokenPreviewRows([1, 2, 3], undefined, 2)
    expect(rows).toEqual([
      { index: 0, id: 1, text: "" },
      { index: 1, id: 2, text: "" }
    ])
  })
})
