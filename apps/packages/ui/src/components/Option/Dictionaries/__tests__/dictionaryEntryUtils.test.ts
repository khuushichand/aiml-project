import { describe, expect, it } from "vitest"
import {
  buildRestorableDictionaryEntryPayload,
  buildTextDiffSegments,
  buildTimedEffectsPayload,
  extractRegexSafetyMessage,
  formatProbabilityFrequencyHint,
  normalizeProbabilityValue,
  toSafeNonNegativeInteger,
  validateRegexPattern,
} from "../components/dictionaryEntryUtils"

describe("dictionaryEntryUtils", () => {
  it("validates regex patterns and reports invalid syntax", () => {
    expect(validateRegexPattern("/foo+/i")).toBeNull()
    expect(validateRegexPattern("hello.*world")).toBeNull()
    expect(validateRegexPattern("[unclosed")).toContain("Invalid")
  })

  it("normalizes safe integers and timed-effects payload shape", () => {
    expect(toSafeNonNegativeInteger(3.8)).toBe(3)
    expect(toSafeNonNegativeInteger(-1)).toBe(0)
    expect(toSafeNonNegativeInteger("5")).toBe(0)

    expect(buildTimedEffectsPayload(undefined)).toBeUndefined()
    expect(buildTimedEffectsPayload({ sticky: "2", cooldown: 5.9, delay: -3 })).toEqual({
      sticky: 0,
      cooldown: 5,
      delay: 0,
    })
    expect(buildTimedEffectsPayload(undefined, { forceObject: true })).toEqual({
      sticky: 0,
      cooldown: 0,
      delay: 0,
    })
  })

  it("clamps probability values and renders frequency hint copy", () => {
    expect(normalizeProbabilityValue(2)).toBe(1)
    expect(normalizeProbabilityValue(-0.3)).toBe(0)
    expect(normalizeProbabilityValue("invalid", 0.42)).toBe(0.42)
    expect(formatProbabilityFrequencyHint(0.56)).toBe("Fires ~6 out of 10 messages (56%).")
  })

  it("builds diff segments for removed and added tokens", () => {
    const segments = buildTextDiffSegments("alpha beta", "alpha gamma")
    expect(segments.some((segment) => segment.type === "removed")).toBe(true)
    expect(segments.some((segment) => segment.type === "added")).toBe(true)
    expect(segments.map((segment) => segment.text).join("")).toContain("alpha")
  })

  it("extracts regex-focused safety message with sensible fallback", () => {
    expect(
      extractRegexSafetyMessage({
        errors: [{ code: "regex_unsafe", field: "entries[0].pattern", message: "Unsafe regex" }],
      })
    ).toBe("Unsafe regex")

    expect(extractRegexSafetyMessage({ errors: [{ message: "Generic validation error" }] })).toBe(
      "Generic validation error"
    )
    expect(extractRegexSafetyMessage({ errors: [] })).toBeNull()
  })

  it("builds restorable payload with normalized defaults", () => {
    const payload = buildRestorableDictionaryEntryPayload({
      pattern: "BP",
      replacement: "blood pressure",
      type: "regex",
      enabled: false,
      case_sensitive: false,
      probability: 2,
      max_replacements: -1,
      group: "Clinical",
      timed_effects: { sticky: 1, cooldown: 2, delay: 3 },
    })

    expect(payload).toEqual({
      pattern: "BP",
      replacement: "blood pressure",
      type: "regex",
      enabled: false,
      case_sensitive: false,
      probability: 1,
      max_replacements: 0,
      group: "Clinical",
      timed_effects: { sticky: 1, cooldown: 2, delay: 3 },
    })
  })
})
