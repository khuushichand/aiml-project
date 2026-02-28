import { describe, expect, it } from "vitest"
import {
  formatLogitBiasValue,
  normalizeLogitBiasValue,
  parseLogitBiasInput,
  withLogitBiasEntry,
  withTokenIdsPresetLogitBias,
  withTokenIdPresetLogitBias,
  withoutLogitBiasEntry
} from "../writing-logit-bias-utils"

describe("writing logit bias utils", () => {
  it("returns null when input is empty", () => {
    expect(parseLogitBiasInput("")).toEqual({ value: null, error: null })
    expect(parseLogitBiasInput("   ")).toEqual({ value: null, error: null })
  })

  it("parses a valid JSON object with finite numeric values", () => {
    const parsed = parseLogitBiasInput('{"50256": -100, "198": -1.5}')
    expect(parsed.error).toBeNull()
    expect(parsed.value).toEqual({
      "198": -1.5,
      "50256": -100
    })
  })

  it("rejects invalid JSON and non-object payloads", () => {
    const invalidJson = parseLogitBiasInput('{"50256"')
    expect(invalidJson.error).toContain("Invalid JSON")
    expect(invalidJson.value).toBeNull()

    const invalidType = parseLogitBiasInput("[1,2,3]")
    expect(invalidType.error).toContain("JSON object")
    expect(invalidType.value).toBeNull()
  })

  it("rejects entries with non-numeric values", () => {
    const parsed = parseLogitBiasInput('{"50256": "bad"}')
    expect(parsed.error).toContain("finite number")
    expect(parsed.value).toBeNull()
  })

  it("formats existing logit bias payloads for editing", () => {
    expect(formatLogitBiasValue({ "50256": -100, "198": -1.5 })).toBe(
      '{\n  "198": -1.5,\n  "50256": -100\n}'
    )
    expect(formatLogitBiasValue(null)).toBe("")
    expect(formatLogitBiasValue({})).toBe("")
  })

  it("normalizes object values and drops invalid entries", () => {
    expect(
      normalizeLogitBiasValue({ "50256": -100, "198": "oops", "42": 1 })
    ).toEqual({})
    expect(
      normalizeLogitBiasValue({ "50256": -100, "42": 1 })
    ).toEqual({
      "42": 1,
      "50256": -100
    })
  })

  it("supports adding and removing individual bias entries", () => {
    const withEntry = withLogitBiasEntry({ "50256": -100 }, "198", -1.5)
    expect(withEntry).toEqual({
      "198": -1.5,
      "50256": -100
    })

    expect(withoutLogitBiasEntry(withEntry, "50256")).toEqual({
      "198": -1.5
    })
  })

  it("applies token-id presets for common bias actions", () => {
    const banned = withTokenIdPresetLogitBias({}, 50256, "ban")
    expect(banned).toEqual({
      "50256": -100
    })

    const favored = withTokenIdPresetLogitBias(banned, "198", "favor")
    expect(favored).toEqual({
      "198": 5,
      "50256": -100
    })
  })

  it("ignores invalid token-id preset input", () => {
    expect(
      withTokenIdPresetLogitBias({ "42": -1 }, Number.NaN, "ban")
    ).toEqual({
      "42": -1
    })
    expect(withTokenIdPresetLogitBias({ "42": -1 }, "   ", "favor")).toEqual({
      "42": -1
    })
  })

  it("applies token-id presets in bulk with deduped ids", () => {
    const next = withTokenIdsPresetLogitBias(
      { "42": -1 },
      [42, 198, 42, "198", "   ", Number.NaN],
      "ban"
    )
    expect(next).toEqual({
      "198": -100,
      "42": -100
    })
  })
})
