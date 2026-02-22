export type MatchingAnswerMap = Record<string, string>

const normalizeComparisonText = (value: unknown): string =>
  String(value ?? "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ")

const parsePairToken = (token: string): [string, string] | null => {
  const trimmed = token.trim()
  if (!trimmed) return null
  const delimiter = trimmed.includes("=>")
    ? "=>"
    : trimmed.includes("::")
      ? "::"
      : null
  if (!delimiter) return null
  const [leftRaw, rightRaw] = trimmed.split(delimiter, 2)
  const left = leftRaw.trim()
  const right = rightRaw.trim()
  if (!left || !right) return null
  return [left, right]
}

export const normalizeMatchingAnswerMap = (value: unknown): MatchingAnswerMap => {
  if (!value) return {}

  if (typeof value === "string") {
    const raw = value.trim()
    if (!raw) return {}
    try {
      const parsed = JSON.parse(raw)
      return normalizeMatchingAnswerMap(parsed)
    } catch {
      const rows = raw.split(/\r?\n|\|\|/g)
      return rows.reduce<MatchingAnswerMap>((acc, row) => {
        const parsed = parsePairToken(row)
        if (!parsed) return acc
        acc[parsed[0]] = parsed[1]
        return acc
      }, {})
    }
  }

  if (Array.isArray(value)) {
    return value.reduce<MatchingAnswerMap>((acc, entry) => {
      if (typeof entry === "string") {
        const parsed = parsePairToken(entry)
        if (parsed) acc[parsed[0]] = parsed[1]
        return acc
      }
      if (Array.isArray(entry) && entry.length >= 2) {
        const left = String(entry[0] ?? "").trim()
        const right = String(entry[1] ?? "").trim()
        if (left && right) acc[left] = right
        return acc
      }
      if (entry && typeof entry === "object") {
        const left = String((entry as { left?: unknown }).left ?? "").trim()
        const right = String((entry as { right?: unknown }).right ?? "").trim()
        if (left && right) acc[left] = right
      }
      return acc
    }, {})
  }

  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>).reduce<MatchingAnswerMap>((acc, [left, rightRaw]) => {
      const leftText = String(left).trim()
      const rightText = String(rightRaw ?? "").trim()
      if (!leftText || !rightText) return acc
      acc[leftText] = rightText
      return acc
    }, {})
  }

  return {}
}

export const buildMatchingPairs = (
  options: string[] | null | undefined,
  correctAnswer: unknown
): Array<{ left: string; right: string }> => {
  const map = normalizeMatchingAnswerMap(correctAnswer)
  const leftOrder = Array.from(
    new Set(
      (options ?? [])
        .map((entry) => String(entry ?? "").trim())
        .filter((entry) => entry.length > 0)
    )
  )

  const rows = leftOrder.map((left) => ({
    left,
    right: map[left] ?? ""
  }))

  Object.entries(map).forEach(([left, right]) => {
    if (leftOrder.includes(left)) return
    rows.push({ left, right })
  })

  return rows
}

const normalizeMatchingCompareMap = (value: unknown): MatchingAnswerMap => {
  const normalized = normalizeMatchingAnswerMap(value)
  return Object.entries(normalized).reduce<MatchingAnswerMap>((acc, [left, right]) => {
    const leftKey = normalizeComparisonText(left)
    const rightValue = normalizeComparisonText(right)
    if (!leftKey || !rightValue) return acc
    acc[leftKey] = rightValue
    return acc
  }, {})
}

export const isMatchingAnswerCorrect = (
  userAnswer: unknown,
  correctAnswer: unknown
): boolean => {
  const userMap = normalizeMatchingCompareMap(userAnswer)
  const correctMap = normalizeMatchingCompareMap(correctAnswer)

  const correctKeys = Object.keys(correctMap)
  if (correctKeys.length === 0) return false
  if (Object.keys(userMap).length !== correctKeys.length) return false

  return correctKeys.every((key) => userMap[key] === correctMap[key])
}

export const formatMatchingAnswer = (value: unknown): string => {
  const entries = Object.entries(normalizeMatchingAnswerMap(value))
  if (entries.length === 0) {
    return String(value ?? "")
  }
  return entries
    .map(([left, right]) => `${left} -> ${right}`)
    .join(" / ")
}
