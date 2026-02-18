import { describe, expect, it } from "vitest"
import {
  buildImportConflictRenameSuggestion,
  buildDictionaryImportErrorDescription,
  isDictionaryImportConflictError,
  validateDictionaryImportData
} from "../importValidationUtils"

describe("dictionary import validation utils", () => {
  it("accepts a valid dictionary import payload", () => {
    const payload = {
      name: "Medical Terms",
      description: "Clinical abbreviations",
      entries: [
        {
          pattern: "BP",
          replacement: "blood pressure",
          type: "literal",
          probability: 1,
          max_replacements: 0
        }
      ]
    }

    const result = validateDictionaryImportData(payload)
    expect(result.valid).toBe(true)
    if (result.valid) {
      expect(result.normalizedData).toEqual(payload)
    }
  })

  it("returns structural errors for missing top-level fields", () => {
    const payload = {
      entries: []
    }
    const result = validateDictionaryImportData(payload)
    expect(result.valid).toBe(false)
    if (!result.valid) {
      expect(result.errors).toContain(
        "Missing required field: name (non-empty string)."
      )
    }
  })

  it("returns entry-level errors for malformed entry definitions", () => {
    const payload = {
      name: "Broken Import",
      entries: [
        {
          replacement: "Doctor",
          type: "pattern",
          probability: 1.2,
          max_replacements: -2,
          timed_effects: { cooldown: -1 }
        }
      ]
    }
    const result = validateDictionaryImportData(payload)
    expect(result.valid).toBe(false)
    if (!result.valid) {
      expect(result.errors).toContain("Entry 1: missing required field `pattern`.")
      expect(result.errors).toContain('Entry 1: type must be "literal" or "regex".')
      expect(result.errors).toContain("Entry 1: probability must be between 0 and 1.")
      expect(result.errors).toContain(
        "Entry 1: max_replacements must be an integer >= 0."
      )
      expect(result.errors).toContain(
        "Entry 1: timed_effects.cooldown must be a number >= 0."
      )
    }
  })

  it("builds conflict-specific remediation hint for import errors", () => {
    const message = buildDictionaryImportErrorDescription(
      new Error("409 conflict: dictionary already exists")
    )
    expect(message).toContain("Try renaming the dictionary")
  })

  it("builds generic remediation hint for non-conflict import errors", () => {
    const message = buildDictionaryImportErrorDescription(
      new Error("Invalid payload")
    )
    expect(message).toContain("Verify the JSON structure")
  })

  it("detects import conflict errors", () => {
    expect(
      isDictionaryImportConflictError(
        new Error("409 conflict: dictionary already exists")
      )
    ).toBe(true)
    expect(isDictionaryImportConflictError(new Error("Invalid payload"))).toBe(
      false
    )
  })

  it("builds deterministic rename suggestions with numeric suffixes", () => {
    const suggestion = buildImportConflictRenameSuggestion("Medical Terms", [
      "Medical Terms",
      "Medical Terms (2)",
      "Medical Terms (3)"
    ])
    expect(suggestion).toBe("Medical Terms (4)")
  })
})
