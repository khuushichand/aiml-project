import { describe, expect, it } from "vitest"

import { buildQuickMessageActionPrompt } from "../quick-message-actions"

describe("buildQuickMessageActionPrompt", () => {
  it("includes quick-action instruction, lineage, and original response", () => {
    const prompt = buildQuickMessageActionPrompt({
      action: "summarize",
      message: "Answer text",
      lineage: "srv:message-1"
    })

    expect(prompt).toContain("Quick action: summarize")
    expect(prompt).toContain("Message lineage: srv:message-1")
    expect(prompt).toContain("Original response:")
    expect(prompt).toContain("Answer text")
  })

  it("injects source references so follow-ups can preserve citation context", () => {
    const prompt = buildQuickMessageActionPrompt({
      action: "shorten",
      message: "Answer with [1] and [2]",
      lineage: "local:abc",
      sourceReferences: ["[1] Source A", "[2] Source B"]
    })

    expect(prompt).toContain("Source references:")
    expect(prompt).toContain("[1] Source A")
    expect(prompt).toContain("[2] Source B")
    expect(prompt).toContain("Keep citation markers like [1], [2]")
  })
})
