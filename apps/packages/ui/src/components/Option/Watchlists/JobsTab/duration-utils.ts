export type DurationUnit = "seconds" | "minutes" | "hours" | "days" | "weeks"

export interface DurationInputValue {
  value: number | null
  unit: DurationUnit
}

const UNIT_TO_SECONDS: Record<DurationUnit, number> = {
  seconds: 1,
  minutes: 60,
  hours: 60 * 60,
  days: 60 * 60 * 24,
  weeks: 60 * 60 * 24 * 7
}

const NORMALIZED_UNITS_DESC: DurationUnit[] = ["weeks", "days", "hours", "minutes", "seconds"]

export const durationToSeconds = (input: DurationInputValue): number | null => {
  if (typeof input.value !== "number" || !Number.isFinite(input.value) || input.value < 0) {
    return null
  }
  const factor = UNIT_TO_SECONDS[input.unit]
  if (!factor) return null
  return Math.floor(input.value) * factor
}

export const secondsToDurationInput = (
  seconds: number | null | undefined,
  defaultUnit: DurationUnit = "days"
): DurationInputValue => {
  if (typeof seconds !== "number" || !Number.isFinite(seconds) || seconds < 0) {
    return {
      value: null,
      unit: defaultUnit
    }
  }

  const normalizedSeconds = Math.floor(seconds)
  for (const unit of NORMALIZED_UNITS_DESC) {
    const factor = UNIT_TO_SECONDS[unit]
    if (normalizedSeconds >= factor && normalizedSeconds % factor === 0) {
      return {
        value: normalizedSeconds / factor,
        unit
      }
    }
  }

  return {
    value: normalizedSeconds,
    unit: "seconds"
  }
}

