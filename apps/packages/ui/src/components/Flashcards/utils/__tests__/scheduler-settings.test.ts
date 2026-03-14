import { describe, expect, it } from "vitest"

import {
  DEFAULT_SCHEDULER_SETTINGS,
  applySchedulerPreset,
  createSchedulerDraft,
  formatSchedulerSummary,
  validateSchedulerDraft
} from "../scheduler-settings"

describe("scheduler-settings utilities", () => {
  it("formats scheduler summaries from normalized settings", () => {
    expect(formatSchedulerSummary(DEFAULT_SCHEDULER_SETTINGS)).toBe(
      "1m,10m -> 1d / easy 4d / leech 8 / fuzz off"
    )
  })

  it("validates draft values using the scheduler rules", () => {
    const draft = createSchedulerDraft({
      ...DEFAULT_SCHEDULER_SETTINGS,
      easy_bonus: 0.8
    })

    draft.new_steps_minutes = "1, 0"
    draft.leech_threshold = "0"

    const result = validateSchedulerDraft(draft)

    expect(result.settings).toBeNull()
    expect(result.errors.new_steps_minutes).toMatch(/positive integers/i)
    expect(result.errors.easy_bonus).toMatch(/>= 1/i)
    expect(result.errors.leech_threshold).toMatch(/>= 1/i)
  })

  it("applies the fast acquisition preset as a normalized settings bundle", () => {
    expect(applySchedulerPreset("fast_acquisition")).toEqual({
      new_steps_minutes: [1, 5, 15],
      relearn_steps_minutes: [10],
      graduating_interval_days: 1,
      easy_interval_days: 3,
      easy_bonus: 1.15,
      interval_modifier: 0.9,
      max_interval_days: 3650,
      leech_threshold: 10,
      enable_fuzz: false
    })
  })
})
