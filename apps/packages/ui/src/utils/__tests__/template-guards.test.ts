import { describe, expect, it } from "vitest"
import {
  hasUnresolvedTemplateTokens,
  withTemplateFallback
} from "@/utils/template-guards"

describe("template-guards", () => {
  it("detects unresolved template tokens", () => {
    expect(hasUnresolvedTemplateTokens("Memory: {{percentage}}% full")).toBe(
      true
    )
    expect(hasUnresolvedTemplateTokens("Memory: 65% full")).toBe(false)
  })

  it("falls back when interpolation tokens remain", () => {
    expect(
      withTemplateFallback(
        "Uses {{model}} · {{task}} · {{format}}",
        "Uses whisper-1 · transcribe · JSON"
      )
    ).toBe("Uses whisper-1 · transcribe · JSON")
  })

  it("keeps resolved translated values", () => {
    expect(
      withTemplateFallback("Sources: Docs/User_Documentation and Docs/Published", "fallback")
    ).toBe("Sources: Docs/User_Documentation and Docs/Published")
  })
})
