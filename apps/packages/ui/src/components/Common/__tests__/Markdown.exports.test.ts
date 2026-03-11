import { describe, expect, it } from "vitest"

import * as MarkdownModule from "../Markdown"

describe("Markdown module exports", () => {
  it("supports both named and default imports for shared consumers", () => {
    expect(MarkdownModule.Markdown).toBeTypeOf("function")
    expect(MarkdownModule.default).toBe(MarkdownModule.Markdown)
  })
})
