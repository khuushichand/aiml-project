import { describe, expect, it } from "vitest"

import {
  filterCopilotPrompts,
  matchesCopilotPromptSearchText
} from "../copilot-prompts-utils"

describe("copilot prompt filter utils", () => {
  const prompts = [
    { key: "summary", prompt: "Summarize {text}" },
    { key: "translate", prompt: "Translate {text} to English" },
    { key: "custom", prompt: "Refine this draft: {text}" }
  ]

  it("matches against key, localized label, and prompt text", () => {
    expect(
      matchesCopilotPromptSearchText(prompts[0], "summarize", "Summary")
    ).toBe(true)
    expect(
      matchesCopilotPromptSearchText(prompts[1], "translate", "Translation")
    ).toBe(true)
    expect(
      matchesCopilotPromptSearchText(prompts[2], "custom", "Custom")
    ).toBe(true)
    expect(
      matchesCopilotPromptSearchText(prompts[0], "nonexistent", "Summary")
    ).toBe(false)
  })

  it("filters by key and query while preserving order", () => {
    const filtered = filterCopilotPrompts(prompts, {
      keyFilter: "translate",
      queryLower: "english",
      resolveKeyLabel: (key) => key
    })
    expect(filtered).toEqual([{ key: "translate", prompt: "Translate {text} to English" }])
  })

  it("returns all items when no filters are set", () => {
    const filtered = filterCopilotPrompts(prompts, {
      keyFilter: "all",
      queryLower: ""
    })
    expect(filtered).toEqual(prompts)
  })
})
