const UNRESOLVED_TEMPLATE_PATTERN = /\{\{\s*[^}]+\s*\}\}/

export const hasUnresolvedTemplateTokens = (
  value: unknown
): value is string => {
  return (
    typeof value === "string" &&
    value.length > 0 &&
    UNRESOLVED_TEMPLATE_PATTERN.test(value)
  )
}

export const withTemplateFallback = (
  candidate: unknown,
  fallback: string
): string => {
  if (typeof candidate !== "string") return fallback
  if (!candidate.trim()) return fallback
  if (hasUnresolvedTemplateTokens(candidate)) return fallback
  return candidate
}
