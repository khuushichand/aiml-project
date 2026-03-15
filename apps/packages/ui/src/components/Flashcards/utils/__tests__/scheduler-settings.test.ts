import { describe, expect, it } from "vitest"

import {
  DEFAULT_FSRS_SCHEDULER_SETTINGS,
  DEFAULT_SCHEDULER_SETTINGS,
  DEFAULT_SCHEDULER_SETTINGS_ENVELOPE,
  applySchedulerPreset,
  createSchedulerDraft,
  formatSchedulerSummary,
  normalizeSchedulerSettingsEnvelope,
  validateSchedulerDraft
} from "../scheduler-settings"

describe("scheduler-settings utilities", () => {
  it("formats scheduler summaries from normalized settings", () => {
    expect(formatSchedulerSummary("sm2_plus", DEFAULT_SCHEDULER_SETTINGS_ENVELOPE)).toBe(
      "1m,10m -> 1d / easy 4d / leech 8 / fuzz off"
    )
    expect(formatSchedulerSummary("fsrs", DEFAULT_SCHEDULER_SETTINGS_ENVELOPE)).toBe(
      "Retention 90% / max 36500d / fuzz off"
    )
    expect(formatSchedulerSummary("sm2_plus", DEFAULT_SCHEDULER_SETTINGS)).toBe(
      "1m,10m -> 1d / easy 4d / leech 8 / fuzz off"
    )
  })

  it("validates draft values using the scheduler rules", () => {
    const draft = createSchedulerDraft({
      schedulerType: "sm2_plus",
      settings: {
        ...DEFAULT_SCHEDULER_SETTINGS_ENVELOPE,
        sm2_plus: {
          ...DEFAULT_SCHEDULER_SETTINGS,
          easy_bonus: 0.8
        }
      }
    })

    draft.sm2_plus.new_steps_minutes = "1, 0"
    draft.sm2_plus.leech_threshold = "0"

    const result = validateSchedulerDraft(draft)

    expect(result.settings).toBeNull()
    expect(result.errors.sm2_plus.new_steps_minutes).toMatch(/positive integers/i)
    expect(result.errors.sm2_plus.easy_bonus).toMatch(/>= 1/i)
    expect(result.errors.sm2_plus.leech_threshold).toMatch(/>= 1/i)
  })

  it("applies the fast acquisition preset as a normalized settings bundle", () => {
    expect(applySchedulerPreset("sm2_plus", "fast_acquisition")).toEqual({
      sm2_plus: {
        new_steps_minutes: [1, 5, 15],
        relearn_steps_minutes: [10],
        graduating_interval_days: 1,
        easy_interval_days: 3,
        easy_bonus: 1.15,
        interval_modifier: 0.9,
        max_interval_days: 3650,
        leech_threshold: 10,
        enable_fuzz: false
      },
      fsrs: DEFAULT_FSRS_SCHEDULER_SETTINGS
    })
  })

  it("normalizes legacy flat scheduler settings into the envelope shape", () => {
    expect(normalizeSchedulerSettingsEnvelope(DEFAULT_SCHEDULER_SETTINGS)).toEqual({
      sm2_plus: DEFAULT_SCHEDULER_SETTINGS,
      fsrs: DEFAULT_FSRS_SCHEDULER_SETTINGS
    })
  })
})
