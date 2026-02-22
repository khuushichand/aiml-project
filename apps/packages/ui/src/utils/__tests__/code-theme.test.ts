import { describe, expect, it } from "vitest"
import { normalizeLanguage } from "../code-theme"

describe("normalizeLanguage", () => {
  it("normalizes text aliases to plaintext", () => {
    expect(normalizeLanguage("text")).toBe("plaintext")
    expect(normalizeLanguage("txt")).toBe("plaintext")
    expect(normalizeLanguage("plain")).toBe("plaintext")
  })

  it("normalizes python shorthand", () => {
    expect(normalizeLanguage("py")).toBe("python")
  })
})
