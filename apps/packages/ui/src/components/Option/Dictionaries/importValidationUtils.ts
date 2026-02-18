type DictionaryImportValidationResult =
  | {
      valid: true
      normalizedData: Record<string, any>
      errors: []
    }
  | {
      valid: false
      normalizedData: null
      errors: string[]
    }

function isRecord(value: unknown): value is Record<string, any> {
  return !!value && typeof value === "object" && !Array.isArray(value)
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value)
}

function safeText(value: unknown): string {
  return typeof value === "string" ? value.trim().toLowerCase() : ""
}

function normalizeExistingNames(existingNames: Array<string | null | undefined>): Set<string> {
  const normalized = new Set<string>()
  for (const name of existingNames) {
    const value = safeText(name)
    if (value) normalized.add(value)
  }
  return normalized
}

function validateTimedEffects(
  timedEffects: unknown,
  entryIndex: number,
  errors: string[]
) {
  if (timedEffects == null) return
  if (!isRecord(timedEffects)) {
    errors.push(`Entry ${entryIndex + 1}: timed_effects must be an object.`)
    return
  }
  for (const key of ["sticky", "cooldown", "delay"] as const) {
    const value = timedEffects[key]
    if (value == null) continue
    if (!isFiniteNumber(value) || value < 0) {
      errors.push(
        `Entry ${entryIndex + 1}: timed_effects.${key} must be a number >= 0.`
      )
    }
  }
}

export function validateDictionaryImportData(
  raw: unknown
): DictionaryImportValidationResult {
  const errors: string[] = []
  if (!isRecord(raw)) {
    return {
      valid: false,
      normalizedData: null,
      errors: ["Top-level JSON must be an object with `name` and `entries`."]
    }
  }

  const name = typeof raw.name === "string" ? raw.name.trim() : ""
  if (!name) {
    errors.push("Missing required field: name (non-empty string).")
  }

  const entries = raw.entries
  if (!Array.isArray(entries)) {
    errors.push("Missing required field: entries (array).")
  } else {
    entries.forEach((entry, index) => {
      if (!isRecord(entry)) {
        errors.push(`Entry ${index + 1}: must be an object.`)
        return
      }

      if (typeof entry.pattern !== "string" || entry.pattern.trim() === "") {
        errors.push(`Entry ${index + 1}: missing required field \`pattern\`.`)
      }
      if (typeof entry.replacement !== "string") {
        errors.push(`Entry ${index + 1}: missing required field \`replacement\`.`)
      }

      if (
        entry.type != null &&
        entry.type !== "literal" &&
        entry.type !== "regex"
      ) {
        errors.push(`Entry ${index + 1}: type must be "literal" or "regex".`)
      }

      if (
        entry.probability != null &&
        (!isFiniteNumber(entry.probability) ||
          entry.probability < 0 ||
          entry.probability > 1)
      ) {
        errors.push(`Entry ${index + 1}: probability must be between 0 and 1.`)
      }

      if (
        entry.max_replacements != null &&
        (!Number.isInteger(entry.max_replacements) || entry.max_replacements < 0)
      ) {
        errors.push(
          `Entry ${index + 1}: max_replacements must be an integer >= 0.`
        )
      }

      validateTimedEffects(entry.timed_effects, index, errors)
    })
  }

  if (errors.length > 0) {
    return {
      valid: false,
      normalizedData: null,
      errors
    }
  }

  return {
    valid: true,
    normalizedData: raw,
    errors: []
  }
}

export function buildDictionaryImportErrorDescription(error: unknown): string {
  const message =
    error instanceof Error && error.message
      ? error.message
      : "Import failed."
  const lower = message.toLowerCase()
  if (
    lower.includes("409") ||
    lower.includes("conflict") ||
    lower.includes("already exists")
  ) {
    return `${message} Try renaming the dictionary or replacing the existing one, then retry.`
  }
  return `${message} Verify the JSON structure (name + entries with pattern/replacement) and retry.`
}

export function isDictionaryImportConflictError(error: unknown): boolean {
  const message =
    error instanceof Error && error.message
      ? error.message
      : String(error || "")
  const lower = message.toLowerCase()
  return (
    lower.includes("409") ||
    lower.includes("conflict") ||
    lower.includes("already exists")
  )
}

export function buildImportConflictRenameSuggestion(
  baseName: string,
  existingNames: Array<string | null | undefined>
): string {
  const cleanBase = baseName.trim() || "Imported Dictionary"
  const normalizedExisting = normalizeExistingNames(existingNames)
  if (!normalizedExisting.has(cleanBase.toLowerCase())) {
    return cleanBase
  }

  let suffix = 2
  while (suffix < 10_000) {
    const candidate = `${cleanBase} (${suffix})`
    if (!normalizedExisting.has(candidate.toLowerCase())) {
      return candidate
    }
    suffix += 1
  }

  return `${cleanBase} (${Date.now()})`
}
