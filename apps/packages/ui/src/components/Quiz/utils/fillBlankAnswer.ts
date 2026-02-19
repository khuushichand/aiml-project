export const DEFAULT_FILL_BLANK_FUZZY_THRESHOLD = 0.88

interface FillBlankAnswerRule {
  value: string
  fuzzy: boolean
  threshold: number
}

interface FillBlankJsonConfig {
  accepted_answers?: unknown
  fuzzy?: unknown
  fuzzy_threshold?: unknown
}

const normalizeAnswerText = (value: unknown): string =>
  String(value ?? "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ")

const clampThreshold = (value: unknown): number => {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return DEFAULT_FILL_BLANK_FUZZY_THRESHOLD
  return Math.min(1, Math.max(0.5, parsed))
}

const toAcceptedAnswers = (value: unknown): string[] => {
  if (!Array.isArray(value)) return []
  return value
    .map((entry) => String(entry ?? "").trim())
    .filter((entry) => entry.length > 0)
}

const parseJsonRules = (raw: string): FillBlankAnswerRule[] | null => {
  if (!(raw.startsWith("{") || raw.startsWith("["))) return null
  try {
    const parsed = JSON.parse(raw) as FillBlankJsonConfig | unknown
    if (Array.isArray(parsed)) {
      const accepted = toAcceptedAnswers(parsed)
      if (accepted.length === 0) return null
      return accepted.map((value) => ({
        value,
        fuzzy: false,
        threshold: DEFAULT_FILL_BLANK_FUZZY_THRESHOLD
      }))
    }
    if (!parsed || typeof parsed !== "object") return null
    const accepted = toAcceptedAnswers((parsed as FillBlankJsonConfig).accepted_answers)
    if (accepted.length === 0) return null
    const fuzzy = Boolean((parsed as FillBlankJsonConfig).fuzzy)
    const threshold = clampThreshold((parsed as FillBlankJsonConfig).fuzzy_threshold)
    return accepted.map((value) => ({
      value,
      fuzzy,
      threshold
    }))
  } catch {
    return null
  }
}

const parseTokenRule = (token: string): FillBlankAnswerRule | null => {
  const trimmed = token.trim()
  if (!trimmed) return null
  if (!trimmed.startsWith("~")) {
    return {
      value: trimmed,
      fuzzy: false,
      threshold: DEFAULT_FILL_BLANK_FUZZY_THRESHOLD
    }
  }
  const body = trimmed.slice(1).trim()
  if (!body) return null
  const thresholdMatch = body.match(/^(\d(?:\.\d+)?)\s*:\s*(.+)$/)
  if (thresholdMatch) {
    return {
      value: thresholdMatch[2].trim(),
      fuzzy: true,
      threshold: clampThreshold(thresholdMatch[1])
    }
  }
  return {
    value: body,
    fuzzy: true,
    threshold: DEFAULT_FILL_BLANK_FUZZY_THRESHOLD
  }
}

const parseRules = (correctAnswer: unknown): FillBlankAnswerRule[] => {
  const raw = String(correctAnswer ?? "").trim()
  if (!raw) return []

  const jsonRules = parseJsonRules(raw)
  if (jsonRules && jsonRules.length > 0) return jsonRules

  const fromDelimited = raw
    .split("||")
    .map((entry) => parseTokenRule(entry))
    .filter((entry): entry is FillBlankAnswerRule => Boolean(entry))
  if (fromDelimited.length > 0) return fromDelimited

  return [
    {
      value: raw,
      fuzzy: false,
      threshold: DEFAULT_FILL_BLANK_FUZZY_THRESHOLD
    }
  ]
}

const levenshteinDistance = (left: string, right: string): number => {
  if (left === right) return 0
  if (left.length === 0) return right.length
  if (right.length === 0) return left.length

  const previous = new Array<number>(right.length + 1)
  const current = new Array<number>(right.length + 1)
  for (let j = 0; j <= right.length; j += 1) previous[j] = j

  for (let i = 1; i <= left.length; i += 1) {
    current[0] = i
    for (let j = 1; j <= right.length; j += 1) {
      const cost = left[i - 1] === right[j - 1] ? 0 : 1
      current[j] = Math.min(
        previous[j] + 1,
        current[j - 1] + 1,
        previous[j - 1] + cost
      )
    }
    for (let j = 0; j <= right.length; j += 1) previous[j] = current[j]
  }
  return previous[right.length]
}

const similarityRatio = (left: string, right: string): number => {
  const maxLen = Math.max(left.length, right.length)
  if (maxLen === 0) return 1
  return 1 - levenshteinDistance(left, right) / maxLen
}

export const isFillBlankAnswerCorrect = (
  userAnswer: unknown,
  correctAnswer: unknown
): boolean => {
  const normalizedUser = normalizeAnswerText(userAnswer)
  if (!normalizedUser) return false

  const rules = parseRules(correctAnswer)
  for (const rule of rules) {
    const normalizedRule = normalizeAnswerText(rule.value)
    if (!normalizedRule) continue
    if (normalizedRule === normalizedUser) return true
    if (rule.fuzzy && similarityRatio(normalizedUser, normalizedRule) >= rule.threshold) {
      return true
    }
  }
  return false
}

export const formatFillBlankAcceptedAnswers = (correctAnswer: unknown): string[] =>
  parseRules(correctAnswer)
    .map((rule) => rule.value.trim())
    .filter((value) => value.length > 0)

