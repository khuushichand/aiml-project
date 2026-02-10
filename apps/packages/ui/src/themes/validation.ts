import type { ThemeColorTokens, ThemeDefinition } from "./types"
import { validateRgbTriple } from "./conversion"

const REQUIRED_TOKEN_KEYS: (keyof ThemeColorTokens)[] = [
  "bg", "surface", "surface2", "elevated",
  "primary", "primaryStrong", "accent",
  "success", "warn", "danger", "muted",
  "border", "borderStrong",
  "text", "textMuted", "textSubtle", "focus",
]

/**
 * Validate that a value has the shape of ThemeColorTokens with valid RGB triples.
 */
export function validateThemeColorTokens(tokens: unknown): tokens is ThemeColorTokens {
  if (!tokens || typeof tokens !== "object") return false
  const obj = tokens as Record<string, unknown>
  return REQUIRED_TOKEN_KEYS.every(
    (key) => typeof obj[key] === "string" && validateRgbTriple(obj[key] as string)
  )
}

/**
 * Validate that a value has the shape of a complete ThemeDefinition.
 */
export function validateThemeDefinition(value: unknown): value is ThemeDefinition {
  if (!value || typeof value !== "object") return false
  const obj = value as Record<string, unknown>
  if (typeof obj.id !== "string" || !obj.id) return false
  if (typeof obj.name !== "string" || !obj.name) return false
  if (typeof obj.builtin !== "boolean") return false
  if (!obj.palette || typeof obj.palette !== "object") return false
  const palette = obj.palette as Record<string, unknown>
  return validateThemeColorTokens(palette.light) && validateThemeColorTokens(palette.dark)
}

/**
 * Generate a unique theme ID from a name.
 * Format: "custom-{slug}-{timestamp36}"
 */
export function generateThemeId(name: string): string {
  const slug = name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 20) || "theme"
  const ts = Date.now().toString(36)
  return `custom-${slug}-${ts}`
}
