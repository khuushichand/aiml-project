import { describe, expect, it } from "vitest"
import {
  buildTokenPreviewRows,
  joinTokenStrings,
  normalizeTokenPreviewText
} from "../writing-token-utils"

describe("writing token utils", () => {
  it("normalizes control characters for preview", () => {
    expect(normalizeTokenPreviewText("a\nb\rc\t")).toBe("a\\nb\\rc\\t")
  })

  it("builds token rows with optional strings", () => {
    const rows = buildTokenPreviewRows([10, 11, 12], ["foo", "\n", "bar"])
    expect(rows).toEqual([
      { index: 0, id: 10, text: "foo", rawText: "foo" },
      { index: 1, id: 11, text: "\\n", rawText: "\n" },
      { index: 2, id: 12, text: "bar", rawText: "bar" }
    ])
  })

  it("truncates rows to maxRows and handles missing strings", () => {
    const rows = buildTokenPreviewRows([1, 2, 3], undefined, 2)
    expect(rows).toEqual([
      { index: 0, id: 1, text: "", rawText: "" },
      { index: 1, id: 2, text: "", rawText: "" }
    ])
  })

  it("joins token strings into raw text", () => {
    expect(joinTokenStrings(["Hello", " ", "world", "\n"])).toBe("Hello world\n")
    expect(joinTokenStrings(undefined)).toBe("")
  })
})
