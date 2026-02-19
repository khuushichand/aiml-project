import { describe, expect, it } from "vitest"
import {
  normalizeCreateDictionaryPayload,
  normalizeDictionaryFormPayload,
  toOptionalPositiveInteger,
} from "../components/dictionaryFormPayloadUtils"

describe("dictionaryFormPayloadUtils", () => {
  describe("toOptionalPositiveInteger", () => {
    it("returns floored positive numbers and undefined for invalid values", () => {
      expect(toOptionalPositiveInteger(8.9)).toBe(8)
      expect(toOptionalPositiveInteger("12.7")).toBe(12)
      expect(toOptionalPositiveInteger("0")).toBeUndefined()
      expect(toOptionalPositiveInteger("abc")).toBeUndefined()
      expect(toOptionalPositiveInteger(null)).toBeUndefined()
    })
  })

  describe("normalizeDictionaryFormPayload", () => {
    it("trims category and normalizes tags and token budget", () => {
      const payload = normalizeDictionaryFormPayload({
        name: "Ops",
        category: "  Team  ",
        tags: ["urgent", "Urgent", " oncall "],
        default_token_budget: "512.9",
      })

      expect(payload).toEqual({
        name: "Ops",
        category: "Team",
        tags: ["urgent", "oncall"],
        default_token_budget: 512,
      })
    })

    it("supports null-preserving options for edit payloads", () => {
      const payload = normalizeDictionaryFormPayload(
        {
          category: "   ",
          tags: [],
          default_token_budget: null,
        },
        {
          allowNullCategory: true,
          includeEmptyTags: true,
          allowNullDefaultTokenBudget: true,
        }
      )

      expect(payload).toEqual({
        category: null,
        tags: [],
        default_token_budget: null,
      })
    })
  })

  describe("normalizeCreateDictionaryPayload", () => {
    it("removes starter_template and empty optional metadata", () => {
      const payload = normalizeCreateDictionaryPayload({
        name: "Medical Glossary",
        category: " ",
        tags: [],
        starter_template: "medical_abbreviations",
      })

      expect(payload).toEqual({
        name: "Medical Glossary",
      })
      expect(payload).not.toHaveProperty("starter_template")
    })
  })
})
