import { describe, expect, it } from "vitest"
import {
  PromptImportValidationError,
  getPromptImportErrorNotice,
  parseImportPromptsPayload
} from "../prompt-import-error-utils"

describe("prompt-import-error-utils", () => {
  it("parses array and object payloads", () => {
    expect(parseImportPromptsPayload('[{"id":"1"}]')).toEqual([{ id: "1" }])
    expect(parseImportPromptsPayload('{"prompts":[{"id":"2"}]}')).toEqual([
      { id: "2" }
    ])
  })

  it("throws typed validation errors for empty, invalid json, and invalid schema", () => {
    expect(() => parseImportPromptsPayload("   ")).toThrowError(
      PromptImportValidationError
    )

    try {
      parseImportPromptsPayload('{"prompts":[}')
      throw new Error("expected invalid json error")
    } catch (error) {
      expect(error).toBeInstanceOf(PromptImportValidationError)
      const typed = error as PromptImportValidationError
      expect(typed.code).toBe("invalid_json")
    }

    try {
      parseImportPromptsPayload('{"foo":"bar"}')
      throw new Error("expected invalid schema error")
    } catch (error) {
      expect(error).toBeInstanceOf(PromptImportValidationError)
      const typed = error as PromptImportValidationError
      expect(typed.code).toBe("invalid_schema")
    }
  })

  it("maps validation errors to user-facing notification copy", () => {
    const emptyNotice = getPromptImportErrorNotice(
      new PromptImportValidationError("empty_file", "empty")
    )
    expect(emptyNotice?.descriptionDefaultValue).toContain("File is empty")

    const schemaNotice = getPromptImportErrorNotice(
      new PromptImportValidationError("invalid_schema", "schema")
    )
    expect(schemaNotice?.descriptionDefaultValue).toContain(
      "File format not recognized"
    )

    const jsonNotice = getPromptImportErrorNotice(
      new PromptImportValidationError("invalid_json", "json", {
        parsePosition: 17
      })
    )
    expect(jsonNotice?.descriptionDefaultValue).toContain("character {{position}}")
    expect(jsonNotice?.values).toEqual({ position: 17 })
  })

  it("returns null for non-import errors", () => {
    expect(getPromptImportErrorNotice(new Error("other"))).toBeNull()
  })
})
