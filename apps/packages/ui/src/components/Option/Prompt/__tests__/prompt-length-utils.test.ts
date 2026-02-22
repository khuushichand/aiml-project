import { describe, expect, it } from "vitest"
import {
  DEFAULT_PROMPT_TOKEN_THRESHOLDS,
  estimatePromptTokens,
  getPromptTokenBudgetState
} from "../prompt-length-utils"

describe("prompt-length-utils", () => {
  it("estimates token counts from character length", () => {
    expect(estimatePromptTokens("")).toBe(0)
    expect(estimatePromptTokens("abcd")).toBe(1)
    expect(estimatePromptTokens("abcde")).toBe(2)
    expect(estimatePromptTokens("a".repeat(4000))).toBe(1000)
  })

  it("maps token counts to normal, warning, and danger budget states", () => {
    expect(getPromptTokenBudgetState(0)).toBe("normal")
    expect(
      getPromptTokenBudgetState(DEFAULT_PROMPT_TOKEN_THRESHOLDS.warning)
    ).toBe("warning")
    expect(
      getPromptTokenBudgetState(DEFAULT_PROMPT_TOKEN_THRESHOLDS.danger)
    ).toBe("danger")

    expect(
      getPromptTokenBudgetState(80, { warning: 100, danger: 200 })
    ).toBe("normal")
    expect(
      getPromptTokenBudgetState(100, { warning: 100, danger: 200 })
    ).toBe("warning")
    expect(
      getPromptTokenBudgetState(250, { warning: 100, danger: 200 })
    ).toBe("danger")
  })
})
