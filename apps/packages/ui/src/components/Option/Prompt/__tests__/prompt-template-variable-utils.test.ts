import { describe, expect, it } from "vitest"
import {
  extractTemplateVariables,
  tokenizeTemplateVariableHighlights,
  validateTemplateVariableSyntax
} from "../prompt-template-variable-utils"

describe("prompt-template-variable-utils", () => {
  it("extracts unique variables in first-seen order with backend-compatible syntax", () => {
    expect(
      extractTemplateVariables(
        "Hello {{ user_name }} and {{topic}} and {{user_name}} and {{ID_2}}"
      )
    ).toEqual(["user_name", "topic", "ID_2"])
  })

  it("tokenizes templates so variable spans can be highlighted", () => {
    const tokens = tokenizeTemplateVariableHighlights(
      "Use {{topic}} with a {{ style_name }} ending."
    )

    expect(tokens.some((token) => token.isVariable && token.variableName === "topic")).toBe(
      true
    )
    expect(
      tokens.some((token) => token.isVariable && token.variableName === "style_name")
    ).toBe(true)
  })

  it("validates unmatched braces and invalid variable names", () => {
    expect(validateTemplateVariableSyntax("Hello {{topic}")).toEqual({
      isValid: false,
      code: "unmatched_braces"
    })

    const invalidName = validateTemplateVariableSyntax("Hello {{bad-name}}")
    expect(invalidName.isValid).toBe(false)
    expect(invalidName.code).toBe("invalid_token")
    expect(invalidName.invalidTokens).toEqual(["{{bad-name}}"])

    expect(validateTemplateVariableSyntax("Hello {{valid_name}}")).toEqual({
      isValid: true
    })
  })
})
