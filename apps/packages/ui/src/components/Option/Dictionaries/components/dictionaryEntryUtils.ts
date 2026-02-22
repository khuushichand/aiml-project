export type InlineEditableEntryField = "pattern" | "replacement"

export type TextDiffSegment = {
  type: "unchanged" | "removed" | "added"
  text: string
}

export function validateRegexPattern(pattern: string): string | null {
  if (!pattern) return null
  try {
    // Check if it looks like a regex pattern (starts and ends with /)
    const regexMatch = pattern.match(/^\/(.*)\/([gimsuvy]*)$/)
    if (regexMatch) {
      new RegExp(regexMatch[1], regexMatch[2])
    } else {
      // Try as plain regex
      new RegExp(pattern)
    }
    return null
  } catch (e: any) {
    return e.message || "Invalid regex pattern"
  }
}

export function toSafeNonNegativeInteger(value: unknown): number {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) {
    return 0
  }
  return Math.floor(value)
}

export function buildTimedEffectsPayload(
  source: unknown,
  options: { forceObject?: boolean } = {}
): { sticky: number; cooldown: number; delay: number } | undefined {
  const forceObject = options.forceObject === true
  const raw =
    source && typeof source === "object"
      ? (source as Record<string, unknown>)
      : null

  if (!raw && !forceObject) {
    return undefined
  }

  const sticky = toSafeNonNegativeInteger(raw?.sticky)
  const cooldown = toSafeNonNegativeInteger(raw?.cooldown)
  const delay = toSafeNonNegativeInteger(raw?.delay)

  if (!forceObject) {
    const hasInput = Boolean(raw) && ["sticky", "cooldown", "delay"].some((key) => {
      const value = raw?.[key]
      return value !== null && value !== undefined && value !== ""
    })
    if (!hasInput) {
      return undefined
    }
  }

  return {
    sticky,
    cooldown,
    delay
  }
}

export function normalizeProbabilityValue(value: unknown, fallback = 1): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return fallback
  }
  return Math.min(1, Math.max(0, value))
}

export function formatProbabilityFrequencyHint(value: unknown): string {
  const normalizedValue = normalizeProbabilityValue(value, 1)
  const percent = Math.round(normalizedValue * 100)
  const outOfTen = Math.round(normalizedValue * 10)
  return `Fires ~${outOfTen} out of 10 messages (${percent}%).`
}

function tokenizeDiffText(source: string): string[] {
  return source.split(/(\s+)/).filter((token) => token.length > 0)
}

function appendDiffSegment(
  segments: TextDiffSegment[],
  type: TextDiffSegment["type"],
  text: string
) {
  if (!text) return
  const previous = segments[segments.length - 1]
  if (previous && previous.type === type) {
    previous.text += text
    return
  }
  segments.push({ type, text })
}

export function buildTextDiffSegments(
  originalText: string,
  processedText: string
): TextDiffSegment[] {
  const originalTokens = tokenizeDiffText(originalText)
  const processedTokens = tokenizeDiffText(processedText)
  const originalLength = originalTokens.length
  const processedLength = processedTokens.length

  if (originalLength === 0 && processedLength === 0) {
    return []
  }

  const lcs: number[][] = Array.from({ length: originalLength + 1 }, () =>
    Array(processedLength + 1).fill(0)
  )

  for (let originalIndex = originalLength - 1; originalIndex >= 0; originalIndex -= 1) {
    for (let processedIndex = processedLength - 1; processedIndex >= 0; processedIndex -= 1) {
      if (originalTokens[originalIndex] === processedTokens[processedIndex]) {
        lcs[originalIndex][processedIndex] = lcs[originalIndex + 1][processedIndex + 1] + 1
      } else {
        lcs[originalIndex][processedIndex] = Math.max(
          lcs[originalIndex + 1][processedIndex],
          lcs[originalIndex][processedIndex + 1]
        )
      }
    }
  }

  const segments: TextDiffSegment[] = []
  let originalIndex = 0
  let processedIndex = 0

  while (originalIndex < originalLength && processedIndex < processedLength) {
    if (originalTokens[originalIndex] === processedTokens[processedIndex]) {
      appendDiffSegment(segments, "unchanged", originalTokens[originalIndex])
      originalIndex += 1
      processedIndex += 1
      continue
    }

    if (lcs[originalIndex + 1][processedIndex] >= lcs[originalIndex][processedIndex + 1]) {
      appendDiffSegment(segments, "removed", originalTokens[originalIndex])
      originalIndex += 1
      continue
    }

    appendDiffSegment(segments, "added", processedTokens[processedIndex])
    processedIndex += 1
  }

  while (originalIndex < originalLength) {
    appendDiffSegment(segments, "removed", originalTokens[originalIndex])
    originalIndex += 1
  }
  while (processedIndex < processedLength) {
    appendDiffSegment(segments, "added", processedTokens[processedIndex])
    processedIndex += 1
  }

  return segments
}

export function extractRegexSafetyMessage(validationReport: any): string | null {
  const errors = Array.isArray(validationReport?.errors)
    ? validationReport.errors
    : []

  if (errors.length === 0) {
    return null
  }

  const regexIssue = errors.find((issue: any) => {
    const code = String(issue?.code || "").toLowerCase()
    const field = String(issue?.field || "").toLowerCase()
    const message = String(issue?.message || "").toLowerCase()
    return (
      code.startsWith("regex_") ||
      field.endsWith(".pattern") ||
      message.includes("regex")
    )
  })

  if (regexIssue?.message) {
    return String(regexIssue.message)
  }

  const firstError = errors[0]
  if (firstError?.message) {
    return String(firstError.message)
  }

  return "Regex pattern failed server validation."
}

export function buildRestorableDictionaryEntryPayload(entry: any): Record<string, any> {
  const payload: Record<string, any> = {
    pattern: typeof entry?.pattern === "string" ? entry.pattern : "",
    replacement: typeof entry?.replacement === "string" ? entry.replacement : "",
    type: entry?.type === "regex" ? "regex" : "literal",
    enabled: typeof entry?.enabled === "boolean" ? entry.enabled : true,
    case_sensitive:
      typeof entry?.case_sensitive === "boolean" ? entry.case_sensitive : true,
    probability:
      typeof entry?.probability === "number" && Number.isFinite(entry.probability)
        ? Math.min(1, Math.max(0, entry.probability))
        : 1,
    max_replacements:
      Number.isInteger(entry?.max_replacements) && entry.max_replacements >= 0
        ? entry.max_replacements
        : 0
  }
  if (typeof entry?.group === "string" && entry.group.trim()) {
    payload.group = entry.group
  }
  if (entry?.timed_effects && typeof entry.timed_effects === "object") {
    payload.timed_effects = entry.timed_effects
  }
  return payload
}
