export const MIN_SCHEDULE_INTERVAL_MINUTES = 5

const CRON_PARTS = 5

const isWildcard = (token: string): boolean => token === "*" || token === "?"

const parseFixedIntegerToken = (token: string): number | null => {
  const parsed = Number(token)
  if (!Number.isInteger(parsed) || parsed < 0) return null
  return parsed
}

const parseStepToken = (token: string): number | null => {
  if (token === "*") return 1
  const match = token.match(/^\*\/(\d+)$/)
  if (!match) return null
  const parsed = Number(match[1])
  if (!Number.isInteger(parsed) || parsed <= 0) return null
  return parsed
}

export interface ScheduleFrequencyAnalysis {
  estimatedIntervalMinutes: number | null
  tooFrequent: boolean
  minAllowedMinutes: number
}

export const estimateScheduleIntervalMinutes = (
  expression: string | null | undefined
): number | null => {
  if (!expression) return null
  const tokens = expression.trim().split(/\s+/)
  if (tokens.length !== CRON_PARTS) return null

  const [minuteToken, hourToken, dayOfMonthToken, monthToken, dayOfWeekToken] = tokens
  const monthIsWildcard = isWildcard(monthToken)
  const dayOfMonthIsWildcard = isWildcard(dayOfMonthToken)
  const dayOfWeekIsWildcard = isWildcard(dayOfWeekToken)
  if (!monthIsWildcard || !dayOfMonthIsWildcard) {
    return null
  }

  const minuteStep = parseStepToken(minuteToken)
  if (minuteStep !== null) {
    if (hourToken === "*" || /^\*\/\d+$/.test(hourToken)) {
      return minuteStep
    }
  }

  const minuteFixed = parseFixedIntegerToken(minuteToken)
  if (minuteFixed === null || minuteFixed > 59) {
    return null
  }

  if (hourToken === "*") {
    return 60
  }

  const hourStep = parseStepToken(hourToken)
  if (hourStep !== null) {
    return hourStep * 60
  }

  const hourFixed = parseFixedIntegerToken(hourToken)
  if (hourFixed === null || hourFixed > 23) {
    return null
  }

  if (dayOfWeekIsWildcard) {
    return 24 * 60
  }

  return 7 * 24 * 60
}

export const analyzeScheduleFrequency = (
  expression: string | null | undefined,
  minAllowedMinutes = MIN_SCHEDULE_INTERVAL_MINUTES
): ScheduleFrequencyAnalysis => {
  const estimatedIntervalMinutes = estimateScheduleIntervalMinutes(expression)
  const tooFrequent =
    typeof estimatedIntervalMinutes === "number" && estimatedIntervalMinutes < minAllowedMinutes
  return {
    estimatedIntervalMinutes,
    tooFrequent,
    minAllowedMinutes
  }
}

export const isScheduleTooFrequent = (
  expression: string | null | undefined,
  minAllowedMinutes = MIN_SCHEDULE_INTERVAL_MINUTES
): boolean => analyzeScheduleFrequency(expression, minAllowedMinutes).tooFrequent
