import { describe, expect, it } from "vitest"
import {
  buildCronFromPreset,
  createDefaultPresetState,
  parsePresetFromCron
} from "../schedule-utils"

describe("schedule-utils", () => {
  it("builds cron expressions from preset state", () => {
    expect(buildCronFromPreset({ preset: "hourly", hour: 9, minute: 15, weekday: "MON" })).toBe(
      "15 * * * *"
    )
    expect(
      buildCronFromPreset({ preset: "every6hours", hour: 9, minute: 0, weekday: "MON" })
    ).toBe("0 */6 * * *")
    expect(buildCronFromPreset({ preset: "daily", hour: 8, minute: 30, weekday: "MON" })).toBe(
      "30 8 * * *"
    )
    expect(buildCronFromPreset({ preset: "weekly", hour: 7, minute: 45, weekday: "FRI" })).toBe(
      "45 7 * * FRI"
    )
  })

  it("parses supported cron patterns into preset state", () => {
    expect(parsePresetFromCron("0 * * * *")).toMatchObject({ preset: "hourly", minute: 0 })
    expect(parsePresetFromCron("15 */6 * * *")).toMatchObject({
      preset: "every6hours",
      minute: 15
    })
    expect(parsePresetFromCron("30 9 * * *")).toEqual({
      preset: "daily",
      hour: 9,
      minute: 30,
      weekday: "MON"
    })
    expect(parsePresetFromCron("5 14 * * TUE")).toEqual({
      preset: "weekly",
      hour: 14,
      minute: 5,
      weekday: "TUE"
    })
  })

  it("returns null for unsupported cron patterns", () => {
    expect(parsePresetFromCron("*/5 * * * *")).toBeNull()
    expect(parsePresetFromCron("0 8 1 * *")).toBeNull()
    expect(parsePresetFromCron("")).toBeNull()
  })

  it("creates a stable default state", () => {
    expect(createDefaultPresetState()).toEqual({
      preset: "daily",
      hour: 9,
      minute: 0,
      weekday: "MON"
    })
  })
})

