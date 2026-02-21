import { describe, expect, it } from "vitest"
import {
  OUTPUT_FORMATTING_GUIDE_SYSTEM_PROMPT_SUFFIX,
  appendSystemPromptSuffix,
  resolveOutputFormattingGuideSuffix
} from "../output-formatting-guide"

describe("output formatting guide prompt helpers", () => {
  it("returns suffix only when enabled", () => {
    expect(resolveOutputFormattingGuideSuffix(false)).toBe("")
    expect(resolveOutputFormattingGuideSuffix(true)).toBe(
      OUTPUT_FORMATTING_GUIDE_SYSTEM_PROMPT_SUFFIX
    )
  })

  it("appends suffix to an existing system prompt", () => {
    const result = appendSystemPromptSuffix(
      "Base system prompt.",
      OUTPUT_FORMATTING_GUIDE_SYSTEM_PROMPT_SUFFIX
    )

    expect(result).toContain("Base system prompt.")
    expect(result).toContain(OUTPUT_FORMATTING_GUIDE_SYSTEM_PROMPT_SUFFIX)
  })

  it("does not append duplicate suffix text", () => {
    const promptWithSuffix = `Base system prompt.\n\n${OUTPUT_FORMATTING_GUIDE_SYSTEM_PROMPT_SUFFIX}`
    const result = appendSystemPromptSuffix(
      promptWithSuffix,
      OUTPUT_FORMATTING_GUIDE_SYSTEM_PROMPT_SUFFIX
    )

    expect(result).toBe(promptWithSuffix)
  })
})
