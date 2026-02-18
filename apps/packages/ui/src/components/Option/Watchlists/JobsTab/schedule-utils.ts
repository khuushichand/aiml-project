export type SchedulePresetKey = "hourly" | "every6hours" | "daily" | "weekly"

export type WeekdayToken = "SUN" | "MON" | "TUE" | "WED" | "THU" | "FRI" | "SAT"

export interface PresetScheduleState {
  preset: SchedulePresetKey
  hour: number
  minute: number
  weekday: WeekdayToken
}

const WEEKDAY_MAP: Record<string, WeekdayToken> = {
  "0": "SUN",
  "1": "MON",
  "2": "TUE",
  "3": "WED",
  "4": "THU",
  "5": "FRI",
  "6": "SAT",
  "7": "SUN",
  SUN: "SUN",
  MON: "MON",
  TUE: "TUE",
  WED: "WED",
  THU: "THU",
  FRI: "FRI",
  SAT: "SAT"
}

const DEFAULT_PRESET_STATE: PresetScheduleState = {
  preset: "daily",
  hour: 9,
  minute: 0,
  weekday: "MON"
}

const clampInteger = (value: unknown, min: number, max: number): number => {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return min
  return Math.min(max, Math.max(min, Math.floor(parsed)))
}

export const normalizeWeekdayToken = (value: unknown): WeekdayToken => {
  if (typeof value !== "string") return DEFAULT_PRESET_STATE.weekday
  return WEEKDAY_MAP[value.toUpperCase()] || DEFAULT_PRESET_STATE.weekday
}

export const buildCronFromPreset = (state: PresetScheduleState): string => {
  const minute = clampInteger(state.minute, 0, 59)
  const hour = clampInteger(state.hour, 0, 23)
  const weekday = normalizeWeekdayToken(state.weekday)

  switch (state.preset) {
    case "hourly":
      return `${minute} * * * *`
    case "every6hours":
      return `${minute} */6 * * *`
    case "weekly":
      return `${minute} ${hour} * * ${weekday}`
    case "daily":
    default:
      return `${minute} ${hour} * * *`
  }
}

export const parsePresetFromCron = (
  expression: string | null | undefined
): PresetScheduleState | null => {
  if (!expression) return null
  const parts = expression.trim().split(/\s+/)
  if (parts.length !== 5) return null

  const [minuteToken, hourToken, dayOfMonthToken, monthToken, dayOfWeekToken] = parts
  if (dayOfMonthToken !== "*" || monthToken !== "*") return null

  const minute = Number(minuteToken)
  if (!Number.isInteger(minute) || minute < 0 || minute > 59) return null

  if (hourToken === "*" && dayOfWeekToken === "*") {
    return {
      preset: "hourly",
      hour: DEFAULT_PRESET_STATE.hour,
      minute,
      weekday: DEFAULT_PRESET_STATE.weekday
    }
  }

  if (hourToken === "*/6" && dayOfWeekToken === "*") {
    return {
      preset: "every6hours",
      hour: DEFAULT_PRESET_STATE.hour,
      minute,
      weekday: DEFAULT_PRESET_STATE.weekday
    }
  }

  const hour = Number(hourToken)
  if (!Number.isInteger(hour) || hour < 0 || hour > 23) return null

  if (dayOfWeekToken === "*") {
    return {
      preset: "daily",
      hour,
      minute,
      weekday: DEFAULT_PRESET_STATE.weekday
    }
  }

  const weekday = WEEKDAY_MAP[dayOfWeekToken.toUpperCase()]
  if (!weekday) return null
  return {
    preset: "weekly",
    hour,
    minute,
    weekday
  }
}

export const createDefaultPresetState = (): PresetScheduleState => ({
  ...DEFAULT_PRESET_STATE
})

