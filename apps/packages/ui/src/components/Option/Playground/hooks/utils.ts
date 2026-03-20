/**
 * Utility / helper functions extracted from PlaygroundForm.
 *
 * These are pure (or near-pure) functions that do not depend on React state
 * and can be consumed by any hook or component.
 */

// ---------------------------------------------------------------------------
// Text helpers
// ---------------------------------------------------------------------------

export const toText = (value: unknown): string =>
  typeof value === "string" ? value : String(value)

export const estimateTokensFromText = (value: string): number => {
  const normalized = value.trim()
  if (!normalized) return 0
  return Math.max(1, Math.ceil(normalized.length / 4))
}

export const collectStringSegments = (
  value: unknown,
  segments: string[],
  depth = 0
): void => {
  if (depth > 4 || value == null) return
  if (typeof value === "string") {
    const trimmed = value.trim()
    if (trimmed.length > 0) {
      segments.push(trimmed)
    }
    return
  }
  if (Array.isArray(value)) {
    value.forEach((entry) => collectStringSegments(entry, segments, depth + 1))
    return
  }
  if (typeof value === "object") {
    Object.values(value as Record<string, unknown>).forEach((entry) =>
      collectStringSegments(entry, segments, depth + 1)
    )
  }
}

// ---------------------------------------------------------------------------
// JSON helpers
// ---------------------------------------------------------------------------

export const parseJsonObject = (
  value?: string
): Record<string, unknown> | undefined => {
  if (!value || typeof value !== "string") return undefined
  const trimmed = value.trim()
  if (!trimmed) return undefined
  try {
    const parsed = JSON.parse(trimmed)
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>
    }
  } catch {
    return undefined
  }
  return undefined
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const CONTEXT_FOOTPRINT_THRESHOLD_PERCENT = 40
