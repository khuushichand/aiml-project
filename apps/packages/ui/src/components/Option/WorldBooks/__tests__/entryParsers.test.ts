import { describe, expect, it } from "vitest"
import { parseBulkEntries } from "../entryParsers"

describe("entryParsers", () => {
  it("parses each supported separator and tracks source lines", () => {
    const raw = [
      "alpha, beta => first entry",
      "gamma -> second entry",
      "delta | third entry",
      "epsilon\tfourth entry"
    ].join("\n")

    const result = parseBulkEntries(raw)

    expect(result.errors).toEqual([])
    expect(result.entries).toEqual([
      { keywords: ["alpha", "beta"], content: "first entry", sourceLine: 1 },
      { keywords: ["gamma"], content: "second entry", sourceLine: 2 },
      { keywords: ["delta"], content: "third entry", sourceLine: 3 },
      { keywords: ["epsilon"], content: "fourth entry", sourceLine: 4 }
    ])
  })

  it("returns line-specific diagnostics for malformed lines", () => {
    const raw = [
      "missing separator line",
      "valid -> line",
      " , => no keywords",
      "keyword_only -> "
    ].join("\n")

    const result = parseBulkEntries(raw)

    expect(result.entries).toEqual([
      { keywords: ["valid"], content: "line", sourceLine: 2 }
    ])
    expect(result.errors).toEqual([
      'Line 1: missing separator (use "keywords -> content")',
      "Line 3: needs keywords and content",
      "Line 4: needs keywords and content"
    ])
  })
})
