import { describe, expect, it } from "vitest"
import {
  MIN_SCHEDULE_INTERVAL_MINUTES,
  analyzeScheduleFrequency,
  estimateScheduleIntervalMinutes,
  isScheduleTooFrequent
} from "../schedule-frequency"

describe("schedule frequency validation", () => {
  it("estimates known cron cadences", () => {
    expect(estimateScheduleIntervalMinutes("* * * * *")).toBe(1)
    expect(estimateScheduleIntervalMinutes("*/5 * * * *")).toBe(5)
    expect(estimateScheduleIntervalMinutes("0 * * * *")).toBe(60)
    expect(estimateScheduleIntervalMinutes("0 */6 * * *")).toBe(360)
    expect(estimateScheduleIntervalMinutes("0 9 * * *")).toBe(1440)
    expect(estimateScheduleIntervalMinutes("0 9 * * MON")).toBe(10080)
  })

  it("flags schedules more frequent than minimum", () => {
    expect(isScheduleTooFrequent("* * * * *")).toBe(true)
    expect(isScheduleTooFrequent("*/4 * * * *")).toBe(true)
    expect(isScheduleTooFrequent("*/5 * * * *")).toBe(false)
  })

  it("returns unknown cadence for unsupported expressions", () => {
    const analysis = analyzeScheduleFrequency("0 9 1 * *", MIN_SCHEDULE_INTERVAL_MINUTES)
    expect(analysis.estimatedIntervalMinutes).toBeNull()
    expect(analysis.tooFrequent).toBe(false)
  })
})
