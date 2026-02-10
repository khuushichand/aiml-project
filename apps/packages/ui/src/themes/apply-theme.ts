import type { ThemeColorTokens } from "./types"

const TOKEN_TO_CSS_VAR: Record<keyof ThemeColorTokens, string> = {
  bg: "--color-bg",
  surface: "--color-surface",
  surface2: "--color-surface-2",
  elevated: "--color-elevated",
  primary: "--color-primary",
  primaryStrong: "--color-primary-strong",
  accent: "--color-accent",
  success: "--color-success",
  warn: "--color-warn",
  danger: "--color-danger",
  muted: "--color-muted",
  border: "--color-border",
  borderStrong: "--color-border-strong",
  text: "--color-text",
  textMuted: "--color-text-muted",
  textSubtle: "--color-text-subtle",
  focus: "--color-focus",
}

const ALL_CSS_VARS = Object.values(TOKEN_TO_CSS_VAR)

/**
 * Apply theme tokens as inline CSS custom properties on `<html>`.
 * Inline styles beat `:root` / `.dark` stylesheet rules in specificity,
 * so the theme overrides the default palette without touching the stylesheet.
 */
export function applyThemeTokens(tokens: ThemeColorTokens): void {
  if (typeof document === "undefined") return
  const style = document.documentElement.style
  for (const [key, cssVar] of Object.entries(TOKEN_TO_CSS_VAR)) {
    style.setProperty(cssVar, tokens[key as keyof ThemeColorTokens])
  }
}

/**
 * Remove all inline theme overrides, falling back to the stylesheet
 * defaults (`:root` / `.dark`). Called when the user selects the "default" theme.
 */
export function clearThemeTokens(): void {
  if (typeof document === "undefined") return
  const style = document.documentElement.style
  for (const cssVar of ALL_CSS_VARS) {
    style.removeProperty(cssVar)
  }
}
