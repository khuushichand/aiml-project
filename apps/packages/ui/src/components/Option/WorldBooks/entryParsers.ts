export interface ParsedBulkEntry {
  keywords: string[]
  content: string
  sourceLine: number
}

export interface BulkParseResult {
  entries: ParsedBulkEntry[]
  errors: string[]
}

export const SUPPORTED_BULK_SEPARATORS = ["=>", "->", "|", "\t"] as const

export function parseBulkEntries(raw: string): BulkParseResult {
  const entries: ParsedBulkEntry[] = []
  const errors: string[] = []

  raw.split(/\r?\n/).forEach((line, index) => {
    const trimmed = line.trim()
    if (!trimmed) return

    const separator = SUPPORTED_BULK_SEPARATORS.find((sep) => trimmed.includes(sep))
    if (!separator) {
      errors.push(`Line ${index + 1}: missing separator (use "keywords -> content")`)
      return
    }

    const [left, ...rest] = trimmed.split(separator)
    const right = rest.join(separator).trim()
    const keywords = left
      .split(",")
      .map((k) => k.trim())
      .filter(Boolean)

    if (keywords.length === 0 || !right) {
      errors.push(`Line ${index + 1}: needs keywords and content`)
      return
    }

    entries.push({ keywords, content: right, sourceLine: index + 1 })
  })

  return { entries, errors }
}
