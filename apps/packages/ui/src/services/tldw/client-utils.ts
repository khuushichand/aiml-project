/**
 * Shared utility functions extracted from TldwApiClient for use by domain method files.
 */

/**
 * Build a URL query string from a params object.
 * Handles arrays (appending multiple values) and skips null/undefined values.
 */
export function buildQuery(params?: Record<string, any>): string {
  if (!params || Object.keys(params).length === 0) {
    return ''
  }
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue
    if (Array.isArray(value)) {
      value.forEach((entry) => search.append(key, String(entry)))
      continue
    }
    search.append(key, String(value))
  }
  const query = search.toString()
  return query ? `?${query}` : ''
}

export function toTrimmedStringArray(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value
      .filter((entry): entry is string => typeof entry === "string" && entry.trim().length > 0)
      .map((entry) => entry.trim())
  }
  if (typeof value === "string" && value.trim().length > 0) {
    return [value.trim()]
  }
  return []
}
