export type WritingWordcloudWordRow = {
  text: string
  weight: number
}

export const parseWordcloudStopwordsInput = (value: string): string[] =>
  String(value || "")
    .split(/[\n,]/)
    .map((entry) => entry.trim())
    .filter(Boolean)

export const normalizeWordcloudWords = (
  words: Array<{ text?: unknown; weight?: unknown }> | undefined,
  maxWords = 100
): WritingWordcloudWordRow[] => {
  if (!Array.isArray(words) || words.length === 0) return []
  const limit = Number.isFinite(maxWords)
    ? Math.max(1, Math.floor(maxWords))
    : 100
  return words
    .map((entry) => {
      const text = String(entry?.text || "").trim()
      const weightRaw = Number(entry?.weight)
      const weight = Number.isFinite(weightRaw) ? Math.floor(weightRaw) : 0
      return { text, weight }
    })
    .filter((entry) => entry.text.length > 0 && entry.weight > 0)
    .sort((left, right) => {
      if (left.weight !== right.weight) {
        return right.weight - left.weight
      }
      return left.text.localeCompare(right.text)
    })
    .slice(0, limit)
}
