import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

describe("PlaygroundForm llama.cpp controls guard", () => {
  it("keeps first-class llama.cpp fields in the preview request payload", () => {
    const formSourcePath = path.resolve(__dirname, "../PlaygroundForm.tsx")
    const formSource = fs.readFileSync(formSourcePath, "utf8")

    expect(formSource).toContain("thinking_budget_tokens:")
    expect(formSource).toContain("grammar_mode:")
    expect(formSource).toContain("grammar_id:")
    expect(formSource).toContain("grammar_inline:")
    expect(formSource).toContain("grammar_override:")
    expect(formSource).toContain("currentChatModelSettings.llamaThinkingBudgetTokens")
    expect(formSource).toContain("currentChatModelSettings.llamaGrammarMode")
    expect(formSource).toContain("currentChatModelSettings.llamaGrammarId")
    expect(formSource).toContain("currentChatModelSettings.llamaGrammarInline")
    expect(formSource).toContain("currentChatModelSettings.llamaGrammarOverride")
  })
})
