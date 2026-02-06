import { describe, expect, it } from "vitest"
import { buildPromptPreviewSummary, estimatePromptTokens } from "../prompt-preview"

describe("prompt preview utility", () => {
  it("classifies sections from prepared prompt messages", () => {
    const summary = buildPromptPreviewSummary([
      { role: "system", content: "You are Ava.\nSpeak tersely." },
      { role: "system", content: "Author's note:\nKeep it concise." },
      { role: "assistant", content: "Hello there." },
      { role: "user", content: "Hi" },
      { role: "assistant", content: "Response" }
    ])

    const byKey = Object.fromEntries(
      summary.sections.map((section) => [section.key, section])
    )

    expect(byKey.character_preset.active).toBe(true)
    expect(byKey.author_note.active).toBe(true)
    expect(byKey.greeting.active).toBe(true)
    expect(byKey.message_steering.active).toBe(false)
    expect(byKey.system_prompt.active).toBe(false)
    expect(summary.budgetStatus).toBe("ok")
  })

  it("classifies steering instructions as message steering", () => {
    const summary = buildPromptPreviewSummary([
      {
        role: "system",
        content:
          "Steering instruction (single response): Continue the user's current thought in the same voice and perspective."
      },
      { role: "user", content: "Hello" }
    ])

    const byKey = Object.fromEntries(
      summary.sections.map((section) => [section.key, section])
    )

    expect(byKey.message_steering.active).toBe(true)
    expect(byKey.message_steering.tokens).toBeGreaterThan(0)
  })

  it("detects overlapping scalar key conflicts", () => {
    const summary = buildPromptPreviewSummary([
      { role: "system", content: "temperature: 0.7" },
      { role: "system", content: "temperature: 0.2" },
      { role: "user", content: "Hi" }
    ])

    expect(
      summary.conflicts.some((conflict) => conflict.type === "scalar_conflict")
    ).toBe(true)
  })

  it("detects contradictory directive conflicts", () => {
    const summary = buildPromptPreviewSummary([
      { role: "system", content: "Speak tersely and stay concise." },
      { role: "system", content: "Be verbose and detailed." },
      { role: "user", content: "Hi" }
    ])

    expect(
      summary.conflicts.some(
        (conflict) => conflict.type === "directive_conflict"
      )
    ).toBe(true)
  })

  it("marks caution budget status above 90 percent", () => {
    const text = "a".repeat(4400)
    const summary = buildPromptPreviewSummary([
      { role: "system", content: text },
      { role: "user", content: "Hi" }
    ])

    expect(summary.supplementalTokens).toBeGreaterThanOrEqual(1080)
    expect(summary.supplementalTokens).toBeLessThan(1200)
    expect(summary.budgetStatus).toBe("caution")
  })

  it("marks error budget status at hard cap", () => {
    const text = "a".repeat(5000)
    const summary = buildPromptPreviewSummary([
      { role: "system", content: text },
      { role: "user", content: "Hi" }
    ])

    expect(summary.supplementalTokens).toBeGreaterThanOrEqual(1200)
    expect(summary.budgetStatus).toBe("error")
  })

  it("estimates tokens using 4 chars per token heuristic", () => {
    expect(estimatePromptTokens("")).toBe(0)
    expect(estimatePromptTokens("abcd")).toBe(1)
    expect(estimatePromptTokens("abcde")).toBe(2)
  })
})
