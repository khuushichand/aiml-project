export interface ReadingTimeEstimateInput {
  wordCount?: number | null
  charCount?: number | null
  wordsPerMinute?: number
}

const DEFAULT_WORDS_PER_MINUTE = 200
const AVERAGE_CHARS_PER_WORD = 5

const toFinitePositive = (value: unknown): number | null => {
  if (typeof value === 'number' && Number.isFinite(value) && value > 0) {
    return value
  }
  if (typeof value === 'string' && value.trim().length > 0) {
    const parsed = Number(value)
    if (Number.isFinite(parsed) && parsed > 0) return parsed
  }
  return null
}

export const estimateReadingTimeMinutes = ({
  wordCount,
  charCount,
  wordsPerMinute = DEFAULT_WORDS_PER_MINUTE
}: ReadingTimeEstimateInput): number | null => {
  const normalizedWpm = toFinitePositive(wordsPerMinute)
  if (!normalizedWpm) return null

  const words = toFinitePositive(wordCount)
  if (words) {
    return Math.max(1, Math.ceil(words / normalizedWpm))
  }

  const chars = toFinitePositive(charCount)
  if (!chars) return null

  const estimatedWords = chars / AVERAGE_CHARS_PER_WORD
  return Math.max(1, Math.ceil(estimatedWords / normalizedWpm))
}
