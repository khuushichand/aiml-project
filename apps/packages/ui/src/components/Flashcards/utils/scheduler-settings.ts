import type {
  DeckSchedulerSettings,
  DeckSchedulerSettingsEnvelope,
  DeckSchedulerType,
  FsrsSchedulerSettings
} from "@/services/flashcards"

type SchedulerSettingsLike =
  | DeckSchedulerSettingsEnvelope
  | DeckSchedulerSettings
  | null
  | undefined

export type SchedulerPresetId =
  | "default"
  | "fast_acquisition"
  | "conservative_review"
  | "high_retention"
  | "long_horizon"

export type Sm2SchedulerSettingsDraft = {
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

export type FsrsSchedulerSettingsDraft = {
  target_retention: string
  maximum_interval_days: string
  enable_fuzz: boolean
}

export type SchedulerSettingsDraft = {
  scheduler_type: DeckSchedulerType
  sm2_plus: Sm2SchedulerSettingsDraft
  fsrs: FsrsSchedulerSettingsDraft
}

export type SchedulerValidationErrors = {
  sm2_plus: Partial<Record<keyof DeckSchedulerSettings, string>>
  fsrs: Partial<Record<keyof FsrsSchedulerSettings, string>>
}

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

export const DEFAULT_FSRS_SCHEDULER_SETTINGS: FsrsSchedulerSettings = {
  target_retention: 0.9,
  maximum_interval_days: 36500,
  enable_fuzz: false
}

export const DEFAULT_SCHEDULER_SETTINGS_ENVELOPE: DeckSchedulerSettingsEnvelope = {
  sm2_plus: DEFAULT_SCHEDULER_SETTINGS,
  fsrs: DEFAULT_FSRS_SCHEDULER_SETTINGS
}

const isSchedulerEnvelope = (
  settings: SchedulerSettingsLike
): settings is DeckSchedulerSettingsEnvelope =>
  typeof settings === "object" &&
  settings !== null &&
  "sm2_plus" in settings

export const normalizeSchedulerSettingsEnvelope = (
  settings: SchedulerSettingsLike
): DeckSchedulerSettingsEnvelope => {
  if (isSchedulerEnvelope(settings)) {
    return {
      sm2_plus: cloneSm2Settings(settings.sm2_plus),
      fsrs: cloneFsrsSettings(settings.fsrs)
    }
  }
  if (settings && typeof settings === "object") {
    return {
      sm2_plus: cloneSm2Settings(settings as DeckSchedulerSettings),
      fsrs: cloneFsrsSettings(DEFAULT_FSRS_SCHEDULER_SETTINGS)
    }
  }
  return {
    sm2_plus: cloneSm2Settings(DEFAULT_SCHEDULER_SETTINGS),
    fsrs: cloneFsrsSettings(DEFAULT_FSRS_SCHEDULER_SETTINGS)
  }
}

const SM2_SCHEDULER_PRESETS: Array<{
  id: Exclude<SchedulerPresetId, "high_retention" | "long_horizon">
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

const FSRS_SCHEDULER_PRESETS: Array<{
  id: Exclude<SchedulerPresetId, "fast_acquisition" | "conservative_review">
  label: string
  description: string
  settings: FsrsSchedulerSettings
}> = [
  {
    id: "default",
    label: "Default",
    description: "Baseline FSRS settings",
    settings: DEFAULT_FSRS_SCHEDULER_SETTINGS
  },
  {
    id: "high_retention",
    label: "High retention",
    description: "Shorter review intervals with a higher recall target",
    settings: {
      target_retention: 0.95,
      maximum_interval_days: 3650,
      enable_fuzz: false
    }
  },
  {
    id: "long_horizon",
    label: "Long horizon",
    description: "Longer review growth for large mature decks",
    settings: {
      target_retention: 0.85,
      maximum_interval_days: 36500,
      enable_fuzz: true
    }
  }
]

const cloneSm2Settings = (settings: DeckSchedulerSettings): DeckSchedulerSettings => ({
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

const cloneFsrsSettings = (settings: FsrsSchedulerSettings): FsrsSchedulerSettings => ({
  target_retention: settings.target_retention,
  maximum_interval_days: settings.maximum_interval_days,
  enable_fuzz: settings.enable_fuzz
})

export const copySchedulerSettings = (settings: DeckSchedulerSettings): DeckSchedulerSettings =>
  cloneSm2Settings(settings)

export const copySchedulerSettingsEnvelope = (
  settings: SchedulerSettingsLike
): DeckSchedulerSettingsEnvelope => normalizeSchedulerSettingsEnvelope(settings)

const formatStepSummary = (steps: number[]): string => {
  if (!steps.length) return "none"
  return steps.map((step) => `${step}m`).join(",")
}

const formatTargetRetention = (value: number): string => `${Math.round(value * 100)}%`

export const formatSchedulerSummary = (
  schedulerType: DeckSchedulerType,
  settings: SchedulerSettingsLike
): string => {
  const normalized = normalizeSchedulerSettingsEnvelope(settings)
  if (schedulerType === "fsrs") {
    return `Retention ${formatTargetRetention(normalized.fsrs.target_retention)} / max ${normalized.fsrs.maximum_interval_days}d / fuzz ${normalized.fsrs.enable_fuzz ? "on" : "off"}`
  }

  const sm2 = normalized.sm2_plus
  return `${formatStepSummary(sm2.new_steps_minutes)} -> ${sm2.graduating_interval_days}d / easy ${sm2.easy_interval_days}d / leech ${sm2.leech_threshold} / fuzz ${sm2.enable_fuzz ? "on" : "off"}`
}

export const createSm2SchedulerDraft = (settings: DeckSchedulerSettings): Sm2SchedulerSettingsDraft => ({
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

export const createFsrsSchedulerDraft = (settings: FsrsSchedulerSettings): FsrsSchedulerSettingsDraft => ({
  target_retention: String(settings.target_retention),
  maximum_interval_days: String(settings.maximum_interval_days),
  enable_fuzz: settings.enable_fuzz
})

export const createSchedulerDraft = ({
  schedulerType = "sm2_plus",
  settings = DEFAULT_SCHEDULER_SETTINGS_ENVELOPE
}: {
  schedulerType?: DeckSchedulerType
  settings?: SchedulerSettingsLike
} = {}): SchedulerSettingsDraft => {
  const envelope = normalizeSchedulerSettingsEnvelope(settings)
  return {
    scheduler_type: schedulerType,
    sm2_plus: createSm2SchedulerDraft(envelope.sm2_plus),
    fsrs: createFsrsSchedulerDraft(envelope.fsrs)
  }
}

export const getSchedulerPresets = (schedulerType: DeckSchedulerType) =>
  schedulerType === "fsrs" ? FSRS_SCHEDULER_PRESETS : SM2_SCHEDULER_PRESETS

export const applySchedulerPreset = (
  schedulerType: DeckSchedulerType,
  presetId: SchedulerPresetId
): DeckSchedulerSettingsEnvelope => {
  const base = copySchedulerSettingsEnvelope(DEFAULT_SCHEDULER_SETTINGS_ENVELOPE)
  if (schedulerType === "fsrs") {
    const preset = FSRS_SCHEDULER_PRESETS.find((candidate) => candidate.id === presetId)
    base.fsrs = cloneFsrsSettings(preset?.settings ?? DEFAULT_FSRS_SCHEDULER_SETTINGS)
    return base
  }
  const preset = SM2_SCHEDULER_PRESETS.find((candidate) => candidate.id === presetId)
  base.sm2_plus = cloneSm2Settings(preset?.settings ?? DEFAULT_SCHEDULER_SETTINGS)
  return base
}

export const resetSchedulerDefaults = (
  draft: SchedulerSettingsDraft
): SchedulerSettingsDraft => {
  const next = createSchedulerDraft({
    schedulerType: draft.scheduler_type,
    settings: copySchedulerSettingsEnvelope(DEFAULT_SCHEDULER_SETTINGS_ENVELOPE)
  })
  return next
}

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

const validateSm2Draft = (
  draft: Sm2SchedulerSettingsDraft
): { settings: DeckSchedulerSettings | null; errors: SchedulerValidationErrors["sm2_plus"] } => {
  const errors: SchedulerValidationErrors["sm2_plus"] = {}

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

const validateFsrsDraft = (
  draft: FsrsSchedulerSettingsDraft
): { settings: FsrsSchedulerSettings | null; errors: SchedulerValidationErrors["fsrs"] } => {
  const errors: SchedulerValidationErrors["fsrs"] = {}
  const targetRetention = parseFloatField(draft.target_retention, "Target retention")
  if (targetRetention.error) errors.target_retention = targetRetention.error

  const maxInterval = parseIntegerField(draft.maximum_interval_days, "Maximum interval")
  if (maxInterval.error) errors.maximum_interval_days = maxInterval.error

  if ((targetRetention.value ?? 0) <= 0 || (targetRetention.value ?? 0) >= 1) {
    errors.target_retention = "Target retention must be between 0 and 1"
  }
  if ((maxInterval.value ?? 0) < 1) {
    errors.maximum_interval_days = "Maximum interval must be >= 1"
  }

  if (Object.keys(errors).length > 0) {
    return { settings: null, errors }
  }

  return {
    settings: {
      target_retention: targetRetention.value!,
      maximum_interval_days: maxInterval.value!,
      enable_fuzz: draft.enable_fuzz
    },
    errors
  }
}

export const validateSchedulerDraft = (
  draft: SchedulerSettingsDraft
): {
  schedulerType: DeckSchedulerType
  settings: DeckSchedulerSettingsEnvelope | null
  errors: SchedulerValidationErrors
} => {
  const sm2 = validateSm2Draft(draft.sm2_plus)
  const fsrs = validateFsrsDraft(draft.fsrs)
  const errors: SchedulerValidationErrors = {
    sm2_plus: sm2.errors,
    fsrs: fsrs.errors
  }

  if (!sm2.settings || !fsrs.settings) {
    return {
      schedulerType: draft.scheduler_type,
      settings: null,
      errors
    }
  }

  return {
    schedulerType: draft.scheduler_type,
    settings: {
      sm2_plus: sm2.settings,
      fsrs: fsrs.settings
    },
    errors
  }
}
