import { describe, expect, it } from "vitest"
import { durationToSeconds, secondsToDurationInput } from "../duration-utils"

describe("duration-utils", () => {
  it("converts duration input to seconds", () => {
    expect(durationToSeconds({ value: 2, unit: "hours" })).toBe(7200)
    expect(durationToSeconds({ value: 1, unit: "weeks" })).toBe(604800)
    expect(durationToSeconds({ value: 0, unit: "days" })).toBe(0)
  })

  it("returns null for invalid duration input", () => {
    expect(durationToSeconds({ value: null, unit: "minutes" })).toBeNull()
    expect(durationToSeconds({ value: -1, unit: "minutes" })).toBeNull()
  })

  it("normalizes seconds into the largest whole unit", () => {
    expect(secondsToDurationInput(86400)).toEqual({ value: 1, unit: "days" })
    expect(secondsToDurationInput(5400)).toEqual({ value: 90, unit: "minutes" })
    expect(secondsToDurationInput(59)).toEqual({ value: 59, unit: "seconds" })
  })

  it("returns empty state for invalid seconds", () => {
    expect(secondsToDurationInput(null)).toEqual({ value: null, unit: "days" })
    expect(secondsToDurationInput(-10, "hours")).toEqual({ value: null, unit: "hours" })
  })
})

