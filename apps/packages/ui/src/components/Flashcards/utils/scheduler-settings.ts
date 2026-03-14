import type { DeckSchedulerSettings } from "@/services/flashcards"

export type SchedulerPresetId = "default" | "fast_acquisition" | "conservative_review"

export type SchedulerSettingsDraft = {
  new_steps_minutes: string
  relearn_steps_minutes: string
  graduating_interval_days: string
  easy_interval_days: string
  easy_bonus: string
  interval_modifier: string
  max_interval_days: string
  leech_threshold: string
  enable_fuzz: boolean
}

export type SchedulerValidationErrors = Partial<Record<keyof DeckSchedulerSettings, string>>

export const DEFAULT_SCHEDULER_SETTINGS: DeckSchedulerSettings = {
  new_steps_minutes: [1, 10],
  relearn_steps_minutes: [10],
  graduating_interval_days: 1,
  easy_interval_days: 4,
  easy_bonus: 1.3,
  interval_modifier: 1,
  max_interval_days: 36500,
  leech_threshold: 8,
  enable_fuzz: false
}

export const SCHEDULER_PRESETS: Array<{
  id: SchedulerPresetId
  label: string
  description: string
  settings: DeckSchedulerSettings
}> = [
  {
    id: "default",
    label: "Default",
    description: "Baseline SM-2+ settings",
    settings: DEFAULT_SCHEDULER_SETTINGS
  },
  {
    id: "fast_acquisition",
    label: "Fast acquisition",
    description: "Shorter early steps and a shorter easy interval",
    settings: {
      new_steps_minutes: [1, 5, 15],
      relearn_steps_minutes: [10],
      graduating_interval_days: 1,
      easy_interval_days: 3,
      easy_bonus: 1.15,
      interval_modifier: 0.9,
      max_interval_days: 3650,
      leech_threshold: 10,
      enable_fuzz: false
    }
  },
  {
    id: "conservative_review",
    label: "Conservative review",
    description: "Slower acquisition with more interval growth and fuzz",
    settings: {
      new_steps_minutes: [10, 60],
      relearn_steps_minutes: [30, 1440],
      graduating_interval_days: 2,
      easy_interval_days: 6,
      easy_bonus: 1.5,
      interval_modifier: 1.1,
      max_interval_days: 36500,
      leech_threshold: 6,
      enable_fuzz: true
    }
  }
]

const formatStepSummary = (steps: number[]): string => {
  if (!steps.length) return "none"
  return steps.map((step) => `${step}m`).join(",")
}

export const formatSchedulerSummary = (settings: DeckSchedulerSettings): string => {
  return `${formatStepSummary(settings.new_steps_minutes)} -> ${settings.graduating_interval_days}d / easy ${settings.easy_interval_days}d / leech ${settings.leech_threshold} / fuzz ${settings.enable_fuzz ? "on" : "off"}`
}

const cloneSettings = (settings: DeckSchedulerSettings): DeckSchedulerSettings => ({
  new_steps_minutes: [...settings.new_steps_minutes],
  relearn_steps_minutes: [...settings.relearn_steps_minutes],
  graduating_interval_days: settings.graduating_interval_days,
  easy_interval_days: settings.easy_interval_days,
  easy_bonus: settings.easy_bonus,
  interval_modifier: settings.interval_modifier,
  max_interval_days: settings.max_interval_days,
  leech_threshold: settings.leech_threshold,
  enable_fuzz: settings.enable_fuzz
})

export const createSchedulerDraft = (settings: DeckSchedulerSettings): SchedulerSettingsDraft => ({
  new_steps_minutes: settings.new_steps_minutes.join(", "),
  relearn_steps_minutes: settings.relearn_steps_minutes.join(", "),
  graduating_interval_days: String(settings.graduating_interval_days),
  easy_interval_days: String(settings.easy_interval_days),
  easy_bonus: String(settings.easy_bonus),
  interval_modifier: String(settings.interval_modifier),
  max_interval_days: String(settings.max_interval_days),
  leech_threshold: String(settings.leech_threshold),
  enable_fuzz: settings.enable_fuzz
})

export const parseSchedulerStepInput = (value: string): number[] => {
  const tokens = value
    .split(",")
    .map((token) => token.trim())
    .filter(Boolean)

  return tokens.map((token) => Number.parseInt(token, 10))
}

const validateStepField = (value: string, fieldName: string): { values: number[]; error?: string } => {
  const values = parseSchedulerStepInput(value)
  if (!value.trim()) {
    return {
      values: [],
      error: `${fieldName} must be a comma-separated list of positive integers`
    }
  }
  if (values.length === 0 || values.some((step) => !Number.isInteger(step) || step <= 0)) {
    return {
      values: [],
      error: `${fieldName} must be a comma-separated list of positive integers`
    }
  }
  if (values.length > 8) {
    return {
      values: [],
      error: `${fieldName} cannot contain more than 8 values`
    }
  }
  return { values }
}

const parseIntegerField = (value: string, fieldName: string): { value: number | null; error?: string } => {
  const parsed = Number.parseInt(value, 10)
  if (!Number.isInteger(parsed)) {
    return {
      value: null,
      error: `${fieldName} must be an integer`
    }
  }
  return { value: parsed }
}

const parseFloatField = (value: string, fieldName: string): { value: number | null; error?: string } => {
  const parsed = Number.parseFloat(value)
  if (!Number.isFinite(parsed)) {
    return {
      value: null,
      error: `${fieldName} must be numeric`
    }
  }
  return { value: parsed }
}

export const validateSchedulerDraft = (
  draft: SchedulerSettingsDraft
): { settings: DeckSchedulerSettings | null; errors: SchedulerValidationErrors } => {
  const errors: SchedulerValidationErrors = {}

  const newSteps = validateStepField(draft.new_steps_minutes, "New steps")
  if (newSteps.error) errors.new_steps_minutes = newSteps.error

  const relearnSteps = validateStepField(draft.relearn_steps_minutes, "Relearn steps")
  if (relearnSteps.error) errors.relearn_steps_minutes = relearnSteps.error

  const graduating = parseIntegerField(draft.graduating_interval_days, "Graduating interval")
  if (graduating.error) errors.graduating_interval_days = graduating.error

  const easyInterval = parseIntegerField(draft.easy_interval_days, "Easy interval")
  if (easyInterval.error) errors.easy_interval_days = easyInterval.error

  const easyBonus = parseFloatField(draft.easy_bonus, "Easy bonus")
  if (easyBonus.error) errors.easy_bonus = easyBonus.error

  const intervalModifier = parseFloatField(draft.interval_modifier, "Interval modifier")
  if (intervalModifier.error) errors.interval_modifier = intervalModifier.error

  const maxInterval = parseIntegerField(draft.max_interval_days, "Max interval")
  if (maxInterval.error) errors.max_interval_days = maxInterval.error

  const leechThreshold = parseIntegerField(draft.leech_threshold, "Leech threshold")
  if (leechThreshold.error) errors.leech_threshold = leechThreshold.error

  if ((graduating.value ?? 0) < 1) {
    errors.graduating_interval_days = "Graduating interval must be >= 1"
  }
  if (
    easyInterval.value != null &&
    graduating.value != null &&
    easyInterval.value < graduating.value
  ) {
    errors.easy_interval_days = "Easy interval must be >= graduating interval"
  }
  if ((easyBonus.value ?? 0) < 1) {
    errors.easy_bonus = "Easy bonus must be >= 1"
  }
  if ((intervalModifier.value ?? 0) <= 0) {
    errors.interval_modifier = "Interval modifier must be > 0"
  }
  if (
    maxInterval.value != null &&
    graduating.value != null &&
    maxInterval.value < graduating.value
  ) {
    errors.max_interval_days = "Max interval must be >= graduating interval"
  }
  if ((leechThreshold.value ?? 0) < 1) {
    errors.leech_threshold = "Leech threshold must be >= 1"
  }

  if (Object.keys(errors).length > 0) {
    return { settings: null, errors }
  }

  return {
    settings: {
      new_steps_minutes: newSteps.values,
      relearn_steps_minutes: relearnSteps.values,
      graduating_interval_days: graduating.value!,
      easy_interval_days: easyInterval.value!,
      easy_bonus: easyBonus.value!,
      interval_modifier: intervalModifier.value!,
      max_interval_days: maxInterval.value!,
      leech_threshold: leechThreshold.value!,
      enable_fuzz: draft.enable_fuzz
    },
    errors
  }
}

export const applySchedulerPreset = (presetId: SchedulerPresetId): DeckSchedulerSettings => {
  const preset = SCHEDULER_PRESETS.find((candidate) => candidate.id === presetId)
  return cloneSettings(preset?.settings ?? DEFAULT_SCHEDULER_SETTINGS)
}

export const copySchedulerSettings = (settings: DeckSchedulerSettings): DeckSchedulerSettings =>
  cloneSettings(settings)
