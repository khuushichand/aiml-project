/** RGB space-separated string, e.g., "47 111 237" */
export type RGBTriple = string

/** The 17 semantic color tokens that drive the entire UI */
export interface ThemeColorTokens {
  bg: RGBTriple
  surface: RGBTriple
  surface2: RGBTriple
  elevated: RGBTriple
  primary: RGBTriple
  primaryStrong: RGBTriple
  accent: RGBTriple
  success: RGBTriple
  warn: RGBTriple
  danger: RGBTriple
  muted: RGBTriple
  border: RGBTriple
  borderStrong: RGBTriple
  text: RGBTriple
  textMuted: RGBTriple
  textSubtle: RGBTriple
  focus: RGBTriple
}

export interface ThemePalette {
  light: ThemeColorTokens
  dark: ThemeColorTokens
}

export interface ThemeDefinition {
  id: string
  name: string
  description?: string
  palette: ThemePalette
  builtin: boolean
}
